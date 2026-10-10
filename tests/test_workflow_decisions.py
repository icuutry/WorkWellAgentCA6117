"""Human checkpoint tests with synthetic in-memory storage, not a real API."""
from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

import app
from contracts import check_result, make_result
import workflow


def check_in(**updates):
    value = {
        "user_id": "demo-user", "date": "2026-10-10", "sitting_hours": 6.0,
        "pain_location": "Neck", "pain_score": 3, "fatigue_score": 4,
        "warning_signs": [], "previous_completion": "Not applicable",
    }
    value.update(updates)
    return value


def draft():
    return {
        "schema_version": 1, "record_id": "server-test-plan", "user_id": "demo-user",
        "date": "2026-10-10", "timestamp": "2026-10-10T09:00:00+08:00",
        "input": check_in(),
        "plan": {"plan_id": "server-test-plan", "actions": [{
            "category": "break", "advice": "Take a brief work break.",
            "reason": "Consider the current sitting time.", "source_ids": ["TEST-01"],
        }]},
        "sources": [{"id": "TEST-01", "title": "Synthetic decision fixture",
                     "content": "Take a brief work break.",
                     "url": "https://example.org/synthetic-decision-fixture"}],
        "plan_status": "awaiting_confirmation", "decision": None, "completion_feedback": None,
    }


def choice(value="accepted", original=None):
    record = deepcopy(original if original is not None else draft())
    record.update(decision=value, plan_status=value, timestamp="2026-10-10T09:10:00+08:00")
    return record


@pytest.fixture
def state(monkeypatch):
    data = SimpleNamespace(records=[draft()], events={}, calls=[], save_arguments=[], external_calls=[])

    def load_history(user_id):
        data.calls.append("history")
        records = [r for r in data.records if r["user_id"] == user_id]
        records.sort(key=lambda r: (r["date"], r["timestamp"]))
        return make_result("ok", data={"records": deepcopy(records)})

    def save_record(record):
        data.calls.append("save_record")
        data.save_arguments.append(deepcopy(record))
        existing = next((r for r in data.records if r["record_id"] == record["record_id"]), None)
        if existing is not None:
            immutable = ("record_id", "user_id", "date", "input", "plan", "sources")
            if any(existing[key] != record[key] for key in immutable):
                return make_result("error", error_code="DUPLICATE_CONFLICT", message="Mismatch")
            if existing["decision"] is not None:
                if existing["decision"] != record["decision"]:
                    return make_result("error", error_code="DUPLICATE_CONFLICT", message="Already final")
                return make_result("saved", data={"record_id": existing["record_id"]})
            existing.clear()
            existing.update(deepcopy(record))
        else:
            data.records.append(deepcopy(record))
        return make_result("saved", data={"record_id": record["record_id"]})

    def append_log(event):
        data.calls.append("log")
        previous = data.events.get(event["event_id"])
        if previous is not None:
            assert previous == event, "An audit retry must have the identical event body."
        data.events[event["event_id"]] = deepcopy(event)
        return make_result("saved", data={"event_id": event["event_id"]})

    def forbidden(*args):
        data.external_calls.append(args)
        raise AssertionError("Decision handling must not generate another plan.")

    data.load_history = load_history
    data.save_record = save_record
    data.append_log = append_log
    monkeypatch.setattr(workflow.storage, "load_history", load_history)
    monkeypatch.setattr(workflow.storage, "save_record", save_record)
    monkeypatch.setattr(workflow.storage, "append_log", append_log)
    monkeypatch.setattr(workflow.retrieval, "retrieve_guidance", forbidden)
    monkeypatch.setattr(workflow.llm, "generate_plan", forbidden)
    monkeypatch.setattr(workflow.feedback, "build_feedback_context", forbidden)
    monkeypatch.setattr(workflow, "_timestamp", lambda: "2026-10-10T09:20:00+08:00")
    return data


def assert_error(result, code):
    check_result(result)
    assert result["status"] == "error" and result["error_code"] == code
    assert "plan" not in result["data"]
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("decision", ["accepted", "rejected"])
def test_explicit_decision_saves_state_and_audit_in_order(state, decision):
    submitted = choice(decision)
    original = deepcopy(submitted)
    result = check_result(workflow.submit_decision(submitted))
    assert result["status"] == "saved" and result["data"] == {"record_id": "server-test-plan"}
    assert state.calls == ["history", "save_record", "log"]
    assert state.records[0]["decision"] == state.records[0]["plan_status"] == decision
    assert state.records[0]["timestamp"] == "2026-10-10T09:20:00+08:00"
    assert state.records[0]["completion_feedback"] is None
    assert state.records[0]["input"] == original["input"]
    assert submitted == original and not state.external_calls
    event = state.events["decision:server-test-plan"]
    assert event["human_decision"] == decision
    assert event["input"] == submitted["input"]
    assert event["source_ids"] == ["TEST-01"]
    assert event["output"]["status"] == decision
    assert event["output"]["trace"] == result["trace"][:-2]
    assert result["trace"][-1]["status"] == decision


@pytest.mark.parametrize("bad", [None, [], {}, "accepted", 1, draft()])
def test_missing_or_implicit_decision_never_calls_storage(state, bad):
    assert_error(workflow.submit_decision(bad), "INVALID_INPUT")
    assert state.calls == [] and not state.events


@pytest.mark.parametrize("missing", list(draft()))
def test_all_record_fields_are_required(state, missing):
    submitted = choice()
    del submitted[missing]
    assert_error(workflow.submit_decision(submitted), "INVALID_INPUT")
    assert state.calls == []


@pytest.mark.parametrize("decision", [None, "auto_accept", "awaiting_confirmation", True, [], {}])
def test_only_accepted_or_rejected_is_a_human_choice(state, decision):
    assert_error(workflow.submit_decision(choice(decision)), "INVALID_INPUT")
    assert state.calls == []


@pytest.mark.parametrize("field,value", [
    ("schema_version", True), ("schema_version", 2), ("plan_status", "rejected"),
    ("timestamp", "2026-10-10T09:10:00"), ("timestamp", "not-a-date"),
    ("completion_feedback", {"completion": "Completed"}), ("record_id", "different-id"),
    ("plan", {}), ("sources", []),
])
def test_invalid_submission_cannot_be_saved(state, field, value):
    submitted = choice()
    submitted[field] = value
    assert_error(workflow.submit_decision(submitted), "INVALID_INPUT")
    assert state.calls == [] and state.records[0]["decision"] is None


def test_nonfinite_or_unserializable_values_are_rejected(state):
    submitted = choice()
    submitted["extra"] = float("nan")
    assert_error(workflow.submit_decision(submitted), "INVALID_INPUT")
    submitted["extra"] = object()
    assert_error(workflow.submit_decision(submitted), "INVALID_INPUT")
    assert state.calls == []


def test_unknown_plan_id_cannot_create_a_final_record(state):
    submitted = choice()
    submitted["record_id"] = submitted["plan"]["plan_id"] = "unknown-plan"
    assert_error(workflow.submit_decision(submitted), "INVALID_INPUT")
    assert state.calls == ["history"] and not state.events


def test_other_users_record_cannot_be_accepted(state):
    submitted = choice()
    submitted["user_id"] = submitted["input"]["user_id"] = "other-user"
    assert_error(workflow.submit_decision(submitted), "INVALID_INPUT")
    assert state.calls == ["history"] and state.records[0]["decision"] is None


@pytest.mark.parametrize("change", ["input", "date", "advice", "reason", "source_title", "source_content", "source_url"])
def test_valid_but_changed_ui_snapshot_is_a_conflict(state, change):
    submitted = choice()
    if change == "input":
        submitted["input"]["fatigue_score"] = 8
    elif change == "date":
        submitted["date"] = submitted["input"]["date"] = "2026-10-11"
    elif change == "advice":
        submitted["plan"]["actions"][0]["advice"] = "Take a work break."
    elif change == "reason":
        submitted["plan"]["actions"][0]["reason"] = "Another reason."
    elif change == "source_title":
        submitted["sources"][0]["title"] = "Different source"
    elif change == "source_content":
        submitted["sources"][0]["content"] += " This is changed."
    else:
        submitted["sources"][0]["url"] = "https://example.org/changed-source"
    assert_error(workflow.submit_decision(submitted), "DUPLICATE_CONFLICT")
    assert state.calls == ["history"] and not state.events
    assert state.records[0]["decision"] is None


def test_warning_input_cannot_be_accepted_even_with_override_field(state):
    submitted = choice()
    submitted["input"].update(warning_signs=["Numbness"], disable_safety=True)
    assert_error(workflow.submit_decision(submitted), "INVALID_INPUT")
    assert state.calls == [] and not state.external_calls


def test_arbitrary_client_metadata_is_not_copied_into_persisted_record(state):
    submitted = choice()
    submitted["disable_safety"] = True
    submitted["automatic_accept"] = "ignore checks"
    assert workflow.submit_decision(submitted)["status"] == "saved"
    assert "disable_safety" not in state.records[0]
    assert "automatic_accept" not in state.records[0]


@pytest.mark.parametrize("decision", ["accepted", "rejected"])
def test_same_decision_retry_keeps_one_record_and_one_identical_audit(state, monkeypatch, decision):
    first = workflow.submit_decision(choice(decision))
    event = deepcopy(next(iter(state.events.values())))
    saved_record = deepcopy(state.records[0])
    state.calls.clear()
    monkeypatch.setattr(workflow, "_timestamp", lambda: "2026-10-11T10:00:00+08:00")
    submitted = choice(decision)
    submitted["timestamp"] = "2026-10-11T10:00:00+08:00"
    second = workflow.submit_decision(submitted)
    assert first["status"] == second["status"] == "saved"
    assert state.calls == ["history", "log"]
    assert state.records == [saved_record] and len(state.events) == 1
    assert next(iter(state.events.values())) == event


@pytest.mark.parametrize("first,second", [("accepted", "rejected"), ("rejected", "accepted")])
def test_a_final_decision_cannot_be_reversed(state, first, second):
    workflow.submit_decision(choice(first))
    before = deepcopy((state.records, state.events))
    state.calls.clear()
    assert_error(workflow.submit_decision(choice(second)), "DUPLICATE_CONFLICT")
    assert (state.records, state.events) == before and state.calls == ["history"]


@pytest.mark.parametrize("problem", ["exception", "error", "unimplemented", "wrong_id", "wrong_status"])
def test_failed_record_save_does_not_report_success_or_write_decision_audit(state, monkeypatch, problem):
    def broken(record):
        if problem == "exception":
            raise OSError("API_KEY=private-secret")
        if problem == "wrong_id":
            return make_result("saved", data={"record_id": "wrong-id"})
        if problem == "wrong_status":
            return make_result("ok", data={"record_id": record["record_id"]})
        return make_result("error", error_code="NOT_IMPLEMENTED" if problem == "unimplemented" else "STORAGE_ERROR",
                           message="API_KEY=private-secret")
    monkeypatch.setattr(workflow.storage, "save_record", broken)
    result = workflow.submit_decision(choice())
    assert_error(result, "NOT_IMPLEMENTED" if problem == "unimplemented" else "STORAGE_ERROR")
    assert not state.events and state.records[0]["decision"] is None
    assert result["data"]["retry_decision"] == "accepted"
    assert "private-secret" not in json.dumps(result)


def test_d_atomic_conflict_is_not_overridden_or_logged_as_success(state, monkeypatch):
    def conflict(record):
        state.records[0].update(decision="rejected", plan_status="rejected")
        return make_result("error", error_code="DUPLICATE_CONFLICT", message="Another final decision")
    monkeypatch.setattr(workflow.storage, "save_record", conflict)
    assert_error(workflow.submit_decision(choice()), "DUPLICATE_CONFLICT")
    assert state.records[0]["decision"] == "rejected" and not state.events


@pytest.mark.parametrize("problem", ["exception", "error", "unimplemented", "wrong_id", "wrong_status"])
def test_failed_audit_reports_partial_save_and_is_retryable(state, monkeypatch, problem):
    def broken(event):
        if problem == "exception":
            raise OSError("API_KEY=private-secret")
        if problem == "wrong_id":
            return make_result("saved", data={"event_id": "wrong-id"})
        if problem == "wrong_status":
            return make_result("ok", data={"event_id": event["event_id"]})
        return make_result("error", error_code="NOT_IMPLEMENTED" if problem == "unimplemented" else "STORAGE_ERROR",
                           message="API_KEY=private-secret")
    monkeypatch.setattr(workflow.storage, "append_log", broken)
    result = workflow.submit_decision(choice())
    assert_error(result, "NOT_IMPLEMENTED" if problem == "unimplemented" else "STORAGE_ERROR")
    assert state.records[0]["decision"] == "accepted"
    assert result["data"] == {"record_id": "server-test-plan", "retry_decision": "accepted"}
    assert "private-secret" not in json.dumps(result)
    monkeypatch.setattr(workflow.storage, "append_log", state.append_log)
    state.calls.clear()
    assert workflow.submit_decision(choice())["status"] == "saved"
    assert state.calls == ["history", "log"] and len(state.events) == 1


@pytest.mark.parametrize("lost_response", ["record", "audit"])
def test_a_durable_write_with_lost_response_recovers_using_the_same_record_and_event(state, monkeypatch, lost_response):
    actual = state.save_record if lost_response == "record" else state.append_log
    name = "save_record" if lost_response == "record" else "append_log"
    def uncertain(value):
        actual(value)
        raise OSError("Lost success response")
    monkeypatch.setattr(workflow.storage, name, uncertain)
    assert_error(workflow.submit_decision(choice()), "STORAGE_ERROR")
    before = deepcopy(state.records[0])
    audit_before = deepcopy(state.events)
    monkeypatch.setattr(workflow.storage, name, actual)
    monkeypatch.setattr(workflow, "_timestamp", lambda: "2026-10-11T10:00:00+08:00")
    result = workflow.submit_decision(choice())
    assert result["status"] == "saved" and state.records == [before]
    assert len(state.events) == 1 and len(state.save_arguments) == 1
    if audit_before:
        assert state.events == audit_before


def test_retry_after_next_day_feedback_preserves_feedback_and_original_audit(state):
    submitted = choice()
    workflow.submit_decision(submitted)
    audit = deepcopy(state.events)
    value = {"completion": "Completed", "reported_date": "2026-10-11", "pain_score": 2, "fatigue_score": 3}
    state.records[0]["completion_feedback"] = value
    state.calls.clear()
    assert workflow.submit_decision(submitted)["status"] == "saved"
    assert state.calls == ["history", "log"]
    assert state.records[0]["completion_feedback"] == value and state.events == audit


def test_corrupt_history_is_not_repaired_or_deleted_by_decision_handling(state):
    state.records[0]["sources"] = []
    before = deepcopy(state.records)
    assert_error(workflow.submit_decision(choice()), "STORAGE_ERROR")
    assert state.records == before and not state.events


def test_history_load_failure_hides_private_details_and_does_not_save(state, monkeypatch):
    def broken(user):
        raise OSError("API_KEY=private-secret")
    monkeypatch.setattr(workflow.storage, "load_history", broken)
    result = workflow.submit_decision(choice())
    assert_error(result, "STORAGE_ERROR")
    assert "private-secret" not in json.dumps(result)
    assert not state.save_arguments and not state.events


@pytest.mark.parametrize("decision", ["accepted", "rejected"])
def test_a_real_adapter_marks_success_only_after_b_saves_the_audit(state, decision):
    current = check_in()
    page_state = {"current": {
        "fingerprint": app.fingerprint(current), "input": deepcopy(current), "decision": None,
        "result": {"status": "awaiting_confirmation", "message": "Synthetic draft",
                   "plan": deepcopy(draft()["plan"]), "sources": deepcopy(draft()["sources"]), "trace": []},
    }}
    backend = app.TeamBackend()
    app.handle_action(page_state, backend, current, decision)
    assert page_state["current"]["decision"] == decision
    app.handle_action(page_state, backend, current, decision)
    assert len(state.save_arguments) == len(state.events) == 1
    assert not state.external_calls


def test_a_keeps_pending_decision_after_partial_save_and_blocks_opposite_button(state, monkeypatch):
    current = check_in()
    page_state = {"current": {
        "fingerprint": app.fingerprint(current), "input": deepcopy(current), "decision": None,
        "result": {"status": "awaiting_confirmation", "message": "Synthetic draft",
                   "plan": deepcopy(draft()["plan"]), "sources": deepcopy(draft()["sources"]), "trace": []},
    }}
    backend = app.TeamBackend()
    monkeypatch.setattr(workflow.storage, "append_log", lambda event: make_result(
        "error", error_code="STORAGE_ERROR", message="Unavailable",
    ))
    with pytest.raises(ValueError):
        app.handle_action(page_state, backend, current, "accepted")
    assert page_state["current"]["decision"] is None
    assert page_state["current"]["pending_record"]["decision"] == "accepted"
    level, message = app.handle_action(page_state, backend, current, "rejected")
    assert level == "warning"
    monkeypatch.setattr(workflow.storage, "append_log", state.append_log)
    app.handle_action(page_state, backend, current, "accepted")
    assert page_state["current"]["decision"] == "accepted"
    assert len(state.save_arguments) == len(state.events) == 1


def test_generate_accept_next_day_feedback_reject_with_actual_b_and_a(state, monkeypatch):
    state.records.clear()
    model_inputs = []
    def context(current, history):
        accepted = [r for r in history if r["decision"] == "accepted" and r["date"] < current["date"]]
        previous = accepted[-1] if accepted else None
        if previous:
            assert previous["completion_feedback"]["reported_date"] == current["date"]
        return make_result("ok", data={"feedback_context": {
            "previous_plan_id": previous["record_id"] if previous else None,
            "previous_actions": previous["plan"]["actions"] if previous else [],
            "completion": current["previous_completion"],
            "previous_pain_score": previous["input"]["pain_score"] if previous else None,
            "current_pain_score": current["pain_score"],
            "previous_fatigue_score": previous["input"]["fatigue_score"] if previous else None,
            "current_fatigue_score": current["fatigue_score"],
        }})
    def save_feedback(user_id, record_id, value):
        old = next(r for r in state.records if r["record_id"] == record_id)
        assert old["decision"] == "accepted" and old["user_id"] == user_id
        old["completion_feedback"] = deepcopy(value)
        return make_result("saved", data={"record_id": record_id})
    def generate(current, value, sources):
        model_inputs.append(deepcopy((current, value, sources)))
        plan = deepcopy(draft()["plan"])
        if value["completion"] == "Partly completed":
            plan["actions"][0]["reason"] = "Previous plan partly completed; consider the current fatigue score."
        return make_result("ok", data={"plan": plan})
    monkeypatch.setattr(workflow.feedback, "build_feedback_context", context)
    monkeypatch.setattr(workflow.storage, "save_feedback", save_feedback)
    monkeypatch.setattr(workflow.retrieval, "retrieve_guidance", lambda current: make_result(
        "ok", data={"sources": deepcopy(draft()["sources"])},
    ))
    monkeypatch.setattr(workflow.llm, "generate_plan", generate)
    backend, page_state = app.TeamBackend(), {}
    first = check_in()
    app.handle_action(page_state, backend, first, "generate")
    assert state.records[0]["decision"] is None
    app.handle_action(page_state, backend, first, "accepted")
    second = check_in(date="2026-10-11", previous_completion="Partly completed", fatigue_score=7)
    app.handle_action(page_state, backend, second, "generate")
    assert model_inputs[1][1]["previous_plan_id"] == state.records[0]["record_id"]
    assert model_inputs[1][1]["completion"] == "Partly completed"
    assert model_inputs[1][1]["current_fatigue_score"] == 7
    assert state.records[0]["completion_feedback"]["reported_date"] == "2026-10-11"
    app.handle_action(page_state, backend, second, "rejected")
    assert [r["decision"] for r in state.records] == ["accepted", "rejected"]
    assert len(model_inputs) == 2 and len(state.events) == 4
    assert len({r["record_id"] for r in state.records}) == 2
