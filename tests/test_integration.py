"""Integration evidence using actual A/B/C/D modules and isolated JSON storage.

Only the external model response is replaced in live-path tests. Offline-path
tests run all modules unchanged. No credentials or network access are required.
"""
import copy
import json
from datetime import date
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import app
import demo_seed
import llm
import retrieval
import storage
import workflow
from contracts import make_result


def check_in(day="2026-10-10", **changes):
    return dict(user_id="demo-user", date=day, sitting_hours=6.0,
                pain_location="Neck", pain_score=3, fatigue_score=4,
                warning_signs=[], previous_completion="Not applicable", **{}) | changes


@pytest.fixture
def model(monkeypatch):
    monkeypatch.delenv("WORKWELL_OFFLINE", raising=False)
    monkeypatch.setattr(llm, "load_env_file", lambda: None)
    calls = []
    knowledge = {s["id"]: s for s in retrieval.load_knowledge()}

    def respond(provider, name, system, user):
        calls.append({"system": system, "user": user})
        source = json.loads(user.split("\n\nSOURCES:\n", 1)[1])[0]
        candidate = source["allowed_actions"][0]
        return json.dumps({"selections": [{"action_id": candidate["action_id"],
                           "priority": 1, "reason": "Use the retrieved guidance for this simulated workday.", "priority_reason": "Main reported need.", "adjustment_reason": "Use the actual daily feedback context."}]})

    monkeypatch.setattr(llm, "_call_model", respond)
    return calls


def records():
    result = storage.load_history("demo-user")
    assert result["status"] == "ok", result
    return result["data"]["records"]


def events():
    return storage.load_logs("demo-user")["data"]["events"]


def generate(state, current):
    app.handle_action(state, app.TeamBackend(), current, "generate")
    result = state["current"]["result"]
    assert result["status"] == "awaiting_confirmation", result
    return result


def decide(state, current, decision):
    level, message = app.handle_action(state, app.TeamBackend(), current, decision)
    assert level == "success", message


def test_complete_three_day_flow_with_rejection_and_real_feedback(model):
    state = {}
    first = check_in()
    generated = generate(state, first)
    first_id = generated["plan"]["plan_id"]
    assert records()[0]["decision"] is None
    decide(state, first, "accepted")
    second = check_in("2026-10-11", previous_completion="Partly completed", fatigue_score=6)
    generate(state, second)
    assert "Partly completed" in model[1]["user"] and first_id in model[1]["user"]
    assert records()[0]["completion_feedback"]["reported_date"] == "2026-10-11"
    decide(state, second, "rejected")
    third = check_in("2026-10-12", previous_completion="Completed", pain_score=2)
    generate(state, third)
    assert first_id in model[2]["user"]
    assert records()[0]["completion_feedback"]["reported_date"] == "2026-10-12"
    assert [r["decision"] for r in records()] == ["accepted", "rejected", None]
    assert len(model) == 3
    assert events()[2]["input"]["previous_completion"] == "Partly completed"


def test_pending_draft_survives_new_session_without_model_recall(model):
    current = check_in()
    first = generate({}, current)
    second = generate({}, current)
    assert first["plan"] == second["plan"]
    assert len(model) == len(records()) == len(events()) == 1


def test_duplicate_buttons_and_reruns_do_not_call_model_or_write_twice(model):
    state, current = {}, check_in()
    generate(state, current)
    generate(state, current)
    decide(state, current, "accepted")
    app.handle_action(state, app.TeamBackend(), current, "accepted")
    assert len(model) == len(records()) == 1 and len(events()) == 2


def test_real_backend_refuses_confirmation_after_input_change(model):
    state, current = {}, check_in()
    generate(state, current)
    changed = current | {"fatigue_score": 8}
    level, _ = app.handle_action(state, app.TeamBackend(), changed, "accepted")
    assert level == "warning" and "current" not in state
    assert records()[0]["decision"] is None


@pytest.mark.parametrize("location", ["None", "Neck", "Shoulders", "Lower back", "Wrists", "Eyes"])
def test_offline_full_pipeline_for_each_discomfort_area(monkeypatch, location):
    monkeypatch.setenv("WORKWELL_OFFLINE", "1")
    result = workflow.start_workflow(check_in(pain_location=location, pain_score=0 if location == "None" else 3))
    assert result["status"] == "awaiting_confirmation", result
    assert result["data"]["mode"] == "offline_demo"
    assert "no model API" in result["message"]
    for action in result["data"]["plan"]["actions"]:
        assert set(action) == {"category", "advice", "reason", "source_ids", "priority", "priority_reason", "adjustment_reason"}


def test_seeded_history_runs_through_actual_workflow(model):
    assert demo_seed.reset_demo_data("with_history")["status"] == "saved"
    result = workflow.start_workflow(demo_seed.DEMO_CHECK_INS["with_history"])
    assert result["status"] == "awaiting_confirmation", result
    assert "demo-seed-2026-10-10" in model[0]["user"]


def test_warning_stops_before_retrieval_and_model(model, monkeypatch):
    monkeypatch.setattr(retrieval, "retrieve_guidance", lambda _: pytest.fail("Retrieval after safety stop"))
    result = workflow.start_workflow(check_in(warning_signs=["Numbness"]))
    assert result["status"] == "stopped" and result["error_code"] == "SAFETY_STOP"
    assert not model and not records()
    assert events()[0]["input"]["warning_signs"] == ["Numbness"]


def test_empty_retrieval_never_calls_model(model):
    result = workflow.start_workflow(check_in(sitting_hours=1, pain_location="None", pain_score=0, fatigue_score=1))
    assert result["error_code"] == "NO_SOURCES" and not model and not records()


@pytest.mark.parametrize("raw", ["bad JSON", '{"actions": []}',
    None, '{"actions":[{"category":[],"advice":"Walk","reason":"r","source_ids":["KB-04"]}]}',
    '{"actions":[{"category":"break","advice":"Walk","reason":"r","source_ids":[{}]}]}',
    '{"actions":[{"category":"break","advice":"Walk","reason":"r","source_ids":["MISSING"]}]}',
    '{"actions":[{"category":"break","advice":"Walk","reason":"r","source_ids":["KB-04"],"extra":"x"}]}'])
def test_invalid_model_json_stops_and_is_logged(model, monkeypatch, raw):
    monkeypatch.setattr(llm, "_call_model", lambda *args: raw)
    result = workflow.start_workflow(check_in())
    assert result["error_code"] == "INVALID_MODEL_OUTPUT", result
    assert not records() and events()[0]["action"] == "workflow_error"


def test_api_error_is_safe_and_retryable(model, monkeypatch):
    actual = llm._call_model
    def fail(*args):
        raise RuntimeError("secret credential must not be displayed")
    monkeypatch.setattr(llm, "_call_model", fail)
    state, current = {}, check_in()
    app.handle_action(state, app.TeamBackend(), current, "generate")
    assert state["current"]["result"]["error_code"] == "MODEL_ERROR"
    assert "secret credential" not in json.dumps(events())
    monkeypatch.setattr(llm, "_call_model", actual)
    generate(state, current)


def test_corrupted_storage_is_preserved_and_model_not_called(model, isolated_runtime_data):
    isolated_runtime_data.mkdir(parents=True)
    path = isolated_runtime_data / "records.json"
    path.write_text("corrupted", encoding="utf-8")
    result = workflow.start_workflow(check_in())
    assert result["error_code"] == "STORAGE_ERROR" and not model
    assert path.read_text(encoding="utf-8") == "corrupted"


def test_partial_decision_audit_failure_recovers_with_same_decision(model, monkeypatch):
    state, current = {}, check_in()
    generate(state, current)
    actual = storage.append_log
    monkeypatch.setattr(storage, "append_log", lambda _: make_result("error", error_code="STORAGE_ERROR", message="Unavailable"))
    level, _ = app.handle_action(state, app.TeamBackend(), current, "accepted")
    assert level == "error" and records()[0]["decision"] == "accepted"
    assert state["current"]["decision"] is None
    assert app.handle_action(state, app.TeamBackend(), current, "rejected")[0] == "warning"
    assert app.handle_action(state, app.TeamBackend(), current | {"date": "2026-10-11"}, "generate")[0] == "warning"
    assert state["current"]["pending_record"]["decision"] == "accepted"
    monkeypatch.setattr(storage, "append_log", actual)
    decide(state, current, "accepted")
    assert len(events()) == 2 and len(model) == 1


def test_team_page_offline_accept_advance_reject_and_reload(monkeypatch):
    monkeypatch.setenv("WORKWELL_OFFLINE", "1")
    ui = AppTest.from_file(str(Path(app.__file__)), default_timeout=20).run()
    assert not ui.exception and ui.radio[0].value == "Team modules"
    ui.date_input[0].set_value(date(2026, 10, 10))
    ui.button[0].click().run()
    assert not ui.exception
    assert ui.session_state["current"]["result"]["mode"] == "offline_demo"
    ui.button[1].click().run()
    assert ui.session_state["current"]["decision"] == "accepted"
    ui.run()
    assert len(records()) == 1 and len(events()) == 2
    ui.button[3].click().run()
    assert ui.date_input[0].value == date(2026, 10, 11)
    ui.selectbox[1].set_value("Partly completed")
    ui.button[0].click().run()
    assert not ui.exception
    assert ui.session_state["current"]["result"]["status"] == "awaiting_confirmation"
    assert 1 <= len(ui.session_state["current"]["result"]["plan"]["actions"]) <= 3
    ui.button[2].click().run()
    assert records()[-1]["decision"] == "rejected"
    reopened = AppTest.from_file(str(Path(app.__file__)), default_timeout=20).run()
    assert not reopened.exception and len(records()) == 2


def test_feedback_cannot_overwrite_a_later_report(model):
    state, current = {}, check_in()
    generate(state, current)
    decide(state, current, "accepted")
    next_day = check_in("2026-10-11", previous_completion="Completed")
    generate(state, next_day)
    saved = records()[0]["completion_feedback"]
    result = storage.save_feedback("demo-user", records()[0]["record_id"], saved | {"pain_score": 1})
    assert result["error_code"] == "DUPLICATE_CONFLICT"


def test_translated_fields_are_refused(model, monkeypatch):
    source = retrieval.retrieve_guidance(check_in())["data"]["sources"][0]
    raw = json.dumps({"actions": [{"category": source["category"], "advice": source["content"],
        "reason": "Retrieved guidance", "source_ids": [source["id"]], "advice_zh": "translation"}]})
    monkeypatch.setattr(llm, "_call_model", lambda *args: raw)
    assert workflow.start_workflow(check_in())["error_code"] == "INVALID_MODEL_OUTPUT"


def test_blank_model_setting_uses_provider_default(model, monkeypatch):
    monkeypatch.setenv("WORKWELL_PROVIDER", "zhipu")
    monkeypatch.setenv("WORKWELL_MODEL", "")
    seen = []
    actual = llm._call_model
    def response(provider, name, system, user):
        seen.append((provider, name))
        return actual(provider, name, system, user)
    monkeypatch.setattr(llm, "_call_model", response)
    generate({}, check_in())
    assert seen == [("zhipu", llm.DEFAULT_MODELS["zhipu"])]
