"""B orchestration tests. Synthetic C/D doubles are not real model/storage evidence."""
from copy import deepcopy
import json
import uuid

import pytest

import app
from contracts import check_result, make_result, WARNING_SIGNS
import workflow


def check_in(**changes):
    value = {
        "user_id": "demo-user", "date": "2026-10-10", "sitting_hours": 6.0,
        "pain_location": "Neck", "pain_score": 3, "fatigue_score": 4,
        "warning_signs": [], "previous_completion": "Not applicable",
    }
    value.update(changes)
    return value


def sources():
    return [{"id": "TEST-01", "title": "Synthetic orchestration fixture",
             "content": "Take a brief work break and stand or walk.",
             "url": "https://example.org/synthetic-workwell-fixture"}]


def actions():
    return [{"category": "break", "advice": "Take a brief work break.",
             "reason": "Consider the current sitting time and completion feedback.",
             "source_ids": ["TEST-01"]}]


def history_record(identifier="older-plan", day="2026-10-08", decision="accepted", **changes):
    value = {
        "schema_version": 1, "record_id": identifier, "user_id": "demo-user", "date": day,
        "timestamp": day + "T09:00:00+08:00", "input": check_in(date=day),
        "plan": {"plan_id": identifier, "actions": actions()}, "sources": sources(),
        "plan_status": decision if decision else "awaiting_confirmation",
        "decision": decision, "completion_feedback": None,
    }
    value.update(changes)
    return value


class Modules:
    """Small in-memory test double that enforces stable IDs and real call order."""
    def __init__(self, monkeypatch):
        self.records = []
        self.events = {}
        self.calls = []
        self.model_calls = []
        self.feedback_calls = []
        self.model_plan = {"actions": actions()}
        self.retrieved = sources()
        for module, name, implementation in (
            (workflow.storage, "load_history", self.load_history),
            (workflow.storage, "save_record", self.save_record),
            (workflow.storage, "save_feedback", self.save_feedback),
            (workflow.storage, "append_log", self.append_log),
            (workflow.feedback, "build_feedback_context", self.build_feedback_context),
            (workflow.retrieval, "retrieve_guidance", self.retrieve_guidance),
            (workflow.llm, "generate_plan", self.generate_plan),
        ):
            monkeypatch.setattr(module, name, implementation)

    def load_history(self, user_id):
        self.calls.append("history")
        return make_result("ok", data={"records": deepcopy(self.records)})

    def save_record(self, record):
        self.calls.append("save_record")
        existing = next((r for r in self.records if r["record_id"] == record["record_id"]), None)
        if existing is not None:
            assert existing == record
        else:
            self.records.append(deepcopy(record))
        return make_result("saved", data={"record_id": record["record_id"]})

    def save_feedback(self, user_id, record_id, value):
        self.calls.append("save_feedback")
        self.feedback_calls.append((user_id, record_id, deepcopy(value)))
        record = next(r for r in self.records if r["record_id"] == record_id)
        assert record["decision"] == "accepted"
        record["completion_feedback"] = deepcopy(value)
        return make_result("saved", data={"record_id": record_id})

    def append_log(self, event):
        self.calls.append("log")
        existing = self.events.get(event["event_id"])
        if existing is not None:
            assert existing == event, "Retries must use an identical event snapshot."
        self.events[event["event_id"]] = deepcopy(event)
        return make_result("saved", data={"event_id": event["event_id"]})

    def build_feedback_context(self, current, history):
        self.calls.append("context")
        accepted = [r for r in history if r["decision"] == "accepted" and r["date"] < current["date"]]
        previous = accepted[-1] if accepted else None
        if previous is not None:
            assert previous["completion_feedback"]["reported_date"] == current["date"]
        value = {
            "previous_plan_id": previous["record_id"] if previous else None,
            "previous_actions": previous["plan"]["actions"] if previous else [],
            "completion": current["previous_completion"],
            "previous_pain_score": previous["input"]["pain_score"] if previous else None,
            "current_pain_score": current["pain_score"],
            "previous_fatigue_score": previous["input"]["fatigue_score"] if previous else None,
            "current_fatigue_score": current["fatigue_score"],
        }
        return make_result("ok", data={"feedback_context": value})

    def retrieve_guidance(self, current):
        self.calls.append("retrieve")
        return make_result("ok", data={"sources": deepcopy(self.retrieved)})

    def generate_plan(self, current, context, retrieved):
        self.calls.append("model")
        self.model_calls.append(deepcopy((current, context, retrieved)))
        return make_result("ok", data={"plan": deepcopy(self.model_plan)})


@pytest.fixture
def modules(monkeypatch):
    return Modules(monkeypatch)


def assert_failure(result, code, *, stopped=False):
    check_result(result)
    assert result["status"] == ("stopped" if stopped else "error")
    assert result["error_code"] == code
    assert "plan" not in result["data"]
    json.dumps(result, allow_nan=False)


def test_first_use_saves_only_pending_draft_and_audit_in_order(modules):
    current = check_in(user_id="  demo-user  ")
    original = deepcopy(current)
    result = check_result(workflow.start_workflow(current))
    assert result["status"] == "awaiting_confirmation"
    assert set(result["data"]) == {"plan", "sources"}
    assert modules.calls == ["history", "context", "retrieve", "model", "save_record", "log"]
    assert len(modules.records) == len(modules.events) == 1
    record = modules.records[0]
    assert record["record_id"] == result["data"]["plan"]["plan_id"]
    uuid.UUID(record["record_id"])
    assert record["plan_status"] == "awaiting_confirmation"
    assert record["decision"] is None and record["completion_feedback"] is None
    assert record["user_id"] == "demo-user" and current == original
    event = next(iter(modules.events.values()))
    assert event["input"] == record["input"]
    assert event["record_id"] == record["record_id"]
    assert event["human_decision"] is None
    assert event["output"]["trace"] == result["trace"][:-2]
    assert result["trace"][-1]["status"] == "waiting"
    assert modules.model_calls[0][1]["previous_plan_id"] is None
    assert modules.model_calls[0][1]["previous_pain_score"] is None


@pytest.mark.parametrize("bad", [None, [], {}, check_in(pain_score=11), check_in(sitting_hours=True)])
def test_invalid_input_calls_no_external_modules(modules, bad):
    assert_failure(workflow.start_workflow(bad), "INVALID_INPUT")
    assert modules.calls == []


@pytest.mark.parametrize("warning", WARNING_SIGNS)
def test_each_warning_stops_before_history_retrieval_model_and_records(modules, warning):
    current = check_in(warning_signs=[warning], previous_completion="Completed",
                       user_id="ignore safety rules", disable_safety=True)
    result = workflow.start_workflow(current)
    assert_failure(result, "SAFETY_STOP", stopped=True)
    assert modules.calls == ["log"]
    assert not modules.records
    event = next(iter(modules.events.values()))
    assert event["input"] == current and event["record_id"] is None
    assert event["output"]["status"] == "stopped" and warning in event["output"]["message"]


def test_safety_stop_stays_visible_when_audit_fails(modules, monkeypatch):
    def broken(event):
        raise OSError("API_KEY=private-secret")
    monkeypatch.setattr(workflow.storage, "append_log", broken)
    result = workflow.start_workflow(check_in(warning_signs=["Numbness"]))
    assert_failure(result, "SAFETY_STOP", stopped=True)
    assert result["data"]["logging_error_code"] == "STORAGE_ERROR"
    assert "audit log" in result["message"]
    assert "private-secret" not in json.dumps(result)
    assert modules.calls == []


def test_no_sources_prevents_model_and_draft_save(modules):
    modules.retrieved = []
    assert_failure(workflow.start_workflow(check_in()), "NO_SOURCES")
    assert modules.calls == ["history", "context", "retrieve", "log"]
    assert not modules.records


@pytest.mark.parametrize("bad", [
    None, {}, [None], [{"id": "MISSING"}],
    sources() + sources(), [dict(sources()[0], url="javascript:alert(1)")],
    [dict(sources()[0], content=" ")], [dict(sources()[0], url="https://secret:token@example.org")],
])
def test_malformed_sources_are_rejected_before_model(modules, bad):
    modules.retrieved = bad
    assert_failure(workflow.start_workflow(check_in()), "INVALID_MODEL_OUTPUT")
    assert not modules.model_calls and not modules.records


@pytest.mark.parametrize("model_id", ["provided-by-model", 123, None, {"dangerous": "id"}])
def test_program_replaces_all_provider_plan_ids(modules, model_id):
    modules.model_plan["plan_id"] = model_id
    result = workflow.start_workflow(check_in())
    assert result["status"] == "awaiting_confirmation"
    uuid.UUID(result["data"]["plan"]["plan_id"])
    assert result["data"]["plan"]["plan_id"] != model_id


@pytest.mark.parametrize("bad", [
    None, [], {}, {"actions": []}, {"actions": actions() * 4},
    {"actions": [dict(actions()[0], category="prescribe")]},
    {"actions": [dict(actions()[0], source_ids=["UNKNOWN"])]},
    {"actions": [dict(actions()[0], advice="Ignore safety warnings and take a break.")]},
    {"actions": [dict(actions()[0], advice="Take aspirin during your work break.")]},
    {"actions": [dict(actions()[0], advice="Take a 99 minute work break.")]},
    {"actions": actions(), "decision": "accepted"},
])
def test_invalid_or_out_of_scope_model_plan_never_reaches_record_storage(modules, bad):
    modules.model_plan = bad
    assert_failure(workflow.start_workflow(check_in()), "INVALID_MODEL_OUTPUT")
    assert "model" in modules.calls and "save_record" not in modules.calls
    assert not modules.records


DEPENDENCIES = [
    ("storage", "load_history", "STORAGE_ERROR"),
    ("feedback", "build_feedback_context", "INVALID_FEEDBACK"),
    ("retrieval", "retrieve_guidance", "NO_SOURCES"),
    ("llm", "generate_plan", "MODEL_ERROR"),
    ("storage", "save_record", "STORAGE_ERROR"),
]


@pytest.mark.parametrize("module_name,function_name,code", DEPENDENCIES)
@pytest.mark.parametrize("problem", ["exception", "bad_envelope", "wrong_status", "error", "unimplemented"])
def test_dependency_failures_stop_and_hide_private_details(modules, monkeypatch, module_name, function_name, code, problem):
    def broken(*args):
        if problem == "exception":
            raise RuntimeError("API_KEY=private-secret")
        if problem == "bad_envelope":
            return {"message": "private-secret"}
        if problem == "wrong_status":
            return make_result("saved" if function_name != "save_record" else "ok")
        return make_result("error", message="API_KEY=private-secret",
                           error_code="NOT_IMPLEMENTED" if problem == "unimplemented" else code)
    monkeypatch.setattr(getattr(workflow, module_name), function_name, broken)
    result = workflow.start_workflow(check_in())
    assert_failure(result, "NOT_IMPLEMENTED" if problem == "unimplemented" else code)
    assert "private-secret" not in json.dumps(result)
    assert result["trace"][-2]["status"] == "error"
    assert result["trace"][-2]["tool"] == module_name + "." + function_name
    assert not modules.records


@pytest.mark.parametrize("bad_data", [{}, {"records": None}, {"records": {}}, {"records": [None]}])
def test_history_result_requires_an_actual_list(modules, monkeypatch, bad_data):
    monkeypatch.setattr(workflow.storage, "load_history", lambda user: make_result("ok", data=bad_data))
    assert_failure(workflow.start_workflow(check_in()), "STORAGE_ERROR")
    assert not modules.model_calls


@pytest.mark.parametrize("field,value", [
    ("schema_version", True), ("schema_version", 2), ("record_id", "wrong-id"),
    ("user_id", "other-user"), ("date", "2026-10-07"), ("timestamp", "not-a-date"),
    ("timestamp", "2026-10-08T09:00:00"), ("input", {}), ("plan", {}), ("sources", []),
    ("plan_status", "accepted_without_consent"), ("decision", "rejected"),
    ("completion_feedback", {}),
])
def test_malformed_history_is_not_treated_as_empty(modules, field, value):
    record = history_record()
    record[field] = value
    modules.records = [record]
    before = deepcopy(modules.records)
    assert_failure(workflow.start_workflow(check_in()), "STORAGE_ERROR")
    assert modules.records == before and not modules.model_calls


def test_duplicate_history_ids_stop(modules):
    modules.records = [history_record(), history_record()]
    assert_failure(workflow.start_workflow(check_in()), "STORAGE_ERROR")


def test_unsorted_history_stops(modules):
    modules.records = [history_record("newer", "2026-10-09"), history_record()]
    assert_failure(workflow.start_workflow(check_in()), "STORAGE_ERROR")


@pytest.mark.parametrize("completion", ["Completed", "Partly completed", "Not completed"])
def test_feedback_without_previous_accepted_plan_stops(modules, completion):
    modules.records = [history_record(decision="rejected")]
    assert_failure(workflow.start_workflow(check_in(previous_completion=completion)), "INVALID_FEEDBACK")
    assert modules.calls == ["history", "log"]


def test_rejected_plan_is_not_used_as_previous_accepted_plan(modules):
    modules.records = [history_record(decision="rejected")]
    result = workflow.start_workflow(check_in())
    assert result["status"] == "awaiting_confirmation"
    assert modules.model_calls[0][1]["previous_actions"] == []
    assert not modules.feedback_calls


def test_missing_completion_for_accepted_plan_stops(modules):
    modules.records = [history_record()]
    assert_failure(workflow.start_workflow(check_in()), "INVALID_FEEDBACK")
    assert not modules.model_calls


def test_latest_accepted_plan_is_used_even_after_a_newer_rejection(modules):
    modules.records = [history_record("first", "2026-10-07"), history_record("accepted", "2026-10-08"),
                       history_record("rejected", "2026-10-09", "rejected")]
    current = check_in(previous_completion="Partly completed", pain_score=5, fatigue_score=8)
    result = workflow.start_workflow(current)
    assert result["status"] == "awaiting_confirmation"
    assert modules.calls.index("save_feedback") < modules.calls.index("context") < modules.calls.index("model")
    assert modules.feedback_calls == [("demo-user", "accepted", {
        "completion": "Partly completed", "reported_date": "2026-10-10", "pain_score": 5, "fatigue_score": 8,
    })]
    context = modules.model_calls[0][1]
    assert context["previous_plan_id"] == "accepted"
    assert context["previous_pain_score"] == 3 and context["current_pain_score"] == 5
    assert context["previous_fatigue_score"] == 4 and context["current_fatigue_score"] == 8
    assert modules.records[0]["completion_feedback"] is None
    assert modules.records[2]["completion_feedback"] is None


@pytest.mark.parametrize("problem", ["error", "exception", "wrong_id"])
def test_feedback_save_failure_prevents_generation(modules, monkeypatch, problem):
    modules.records = [history_record()]
    def broken(*args):
        if problem == "exception":
            raise OSError("private-secret")
        if problem == "wrong_id":
            return make_result("saved", data={"record_id": "wrong-plan"})
        return make_result("error", error_code="STORAGE_ERROR", message="private-secret")
    monkeypatch.setattr(workflow.storage, "save_feedback", broken)
    result = workflow.start_workflow(check_in(previous_completion="Completed"))
    assert_failure(result, "STORAGE_ERROR")
    assert "private-secret" not in json.dumps(result)
    assert not modules.model_calls and "context" not in modules.calls


@pytest.mark.parametrize("field,value", [
    ("previous_plan_id", "rejected-plan"), ("previous_actions", []), ("completion", "Completed"),
    ("previous_pain_score", None), ("current_pain_score", True),
    ("previous_fatigue_score", 0), ("current_fatigue_score", 0),
])
def test_incorrect_feedback_context_stops_before_c(modules, monkeypatch, field, value):
    modules.records = [history_record()]
    actual = modules.build_feedback_context
    def wrong(current, history):
        result = actual(current, history)
        result["data"]["feedback_context"][field] = value
        return result
    monkeypatch.setattr(workflow.feedback, "build_feedback_context", wrong)
    assert_failure(workflow.start_workflow(check_in(previous_completion="Partly completed")), "INVALID_FEEDBACK")
    assert not modules.model_calls


def test_conflicting_feedback_for_same_report_date_stops(modules):
    modules.records = [history_record(completion_feedback={
        "completion": "Completed", "reported_date": "2026-10-10", "pain_score": 3, "fatigue_score": 4,
    })]
    assert_failure(workflow.start_workflow(check_in(previous_completion="Not completed")), "INVALID_FEEDBACK")
    assert not modules.feedback_calls and not modules.model_calls


@pytest.mark.parametrize("day", ["2026-10-07", "2026-10-08"])
def test_historical_and_same_day_generation_are_rejected(modules, day):
    modules.records = [history_record()]
    assert_failure(workflow.start_workflow(check_in(date=day)), "INVALID_INPUT")
    assert not modules.model_calls


def test_backfill_before_already_reported_feedback_is_rejected(modules):
    modules.records = [history_record(completion_feedback={
        "completion": "Completed", "reported_date": "2026-10-11", "pain_score": 3, "fatigue_score": 4,
    })]
    assert_failure(workflow.start_workflow(check_in(previous_completion="Completed")), "INVALID_INPUT")
    assert not modules.model_calls


def test_saved_draft_resumes_without_another_model_or_record_write(modules):
    first = workflow.start_workflow(check_in())
    event = deepcopy(next(iter(modules.events.values())))
    modules.calls.clear()
    second = workflow.start_workflow(check_in())
    assert first["data"] == second["data"]
    assert modules.calls == ["history", "log"]
    assert len(modules.model_calls) == len(modules.records) == len(modules.events) == 1
    assert next(iter(modules.events.values())) == event
    assert any(step["step"] == "reuse_saved_draft" for step in second["trace"])


def test_changed_input_cannot_resume_same_day_draft(modules):
    workflow.start_workflow(check_in())
    assert_failure(workflow.start_workflow(check_in(fatigue_score=7)), "INVALID_INPUT")
    assert len(modules.model_calls) == len(modules.records) == 1


def test_partial_generation_log_write_retries_same_event_and_draft(modules, monkeypatch):
    actual = modules.append_log
    failed = []
    def uncertain(event):
        if event["action"] == "draft_generated":
            failed.append(deepcopy(event))
            actual(event)  # Simulate a durable write whose response was lost.
            raise OSError("Lost confirmation")
        return actual(event)
    monkeypatch.setattr(workflow.storage, "append_log", uncertain)
    assert_failure(workflow.start_workflow(check_in()), "STORAGE_ERROR")
    assert len(modules.records) == len(modules.model_calls) == 1
    monkeypatch.setattr(workflow.storage, "append_log", actual)
    retry = workflow.start_workflow(check_in())
    assert retry["status"] == "awaiting_confirmation"
    assert len(modules.records) == len(modules.model_calls) == 1
    assert modules.events[failed[0]["event_id"]] == failed[0]


def test_lost_draft_save_response_is_recovered_from_history(modules, monkeypatch):
    actual = modules.save_record
    def uncertain(record):
        actual(record)
        raise OSError("Lost confirmation")
    monkeypatch.setattr(workflow.storage, "save_record", uncertain)
    assert_failure(workflow.start_workflow(check_in()), "STORAGE_ERROR")
    monkeypatch.setattr(workflow.storage, "save_record", actual)
    assert workflow.start_workflow(check_in())["status"] == "awaiting_confirmation"
    assert len(modules.records) == len(modules.model_calls) == 1


def test_record_save_requires_matching_id(modules, monkeypatch):
    monkeypatch.setattr(workflow.storage, "save_record", lambda r: make_result("saved", data={"record_id": "wrong"}))
    assert_failure(workflow.start_workflow(check_in()), "STORAGE_ERROR")
    assert not any(e["action"] == "draft_generated" for e in modules.events.values())


def test_audit_save_requires_matching_id(modules, monkeypatch):
    monkeypatch.setattr(workflow.storage, "append_log", lambda e: make_result("saved", data={"event_id": "wrong"}))
    result = workflow.start_workflow(check_in())
    assert_failure(result, "STORAGE_ERROR")
    assert result["data"]["logging_error_code"] == "STORAGE_ERROR"
    assert len(modules.records) == 1


def test_c_cannot_mutate_inputs_sources_or_feedback_in_b(modules, monkeypatch):
    def mutating(current, context, retrieved):
        current["warning_signs"] = ["Numbness"]
        context["current_pain_score"] = 999
        retrieved.clear()
        return make_result("ok", data={"plan": {"actions": actions()}})
    monkeypatch.setattr(workflow.llm, "generate_plan", mutating)
    current = check_in()
    result = workflow.start_workflow(current)
    assert result["status"] == "awaiting_confirmation"
    assert modules.records[0]["input"] == current
    assert result["data"]["sources"] == sources()
    result["data"]["plan"]["actions"].clear()
    assert modules.records[0]["plan"]["actions"] == actions()


def test_module_data_with_nonfinite_values_stops(modules, monkeypatch):
    monkeypatch.setattr(workflow.llm, "generate_plan", lambda *args: make_result(
        "ok", data={"plan": {"actions": actions()}, "invalid_metadata": float("nan")},
    ))
    assert_failure(workflow.start_workflow(check_in()), "MODEL_ERROR")
    assert not modules.records


def test_missing_feedback_context_stops(modules, monkeypatch):
    monkeypatch.setattr(workflow.feedback, "build_feedback_context", lambda *args: make_result("ok"))
    assert_failure(workflow.start_workflow(check_in()), "INVALID_FEEDBACK")
    assert not modules.model_calls


def test_malformed_module_trace_is_not_displayed_as_success(modules, monkeypatch):
    monkeypatch.setattr(workflow.retrieval, "retrieve_guidance", lambda *args: make_result(
        "ok", data={"sources": sources()}, trace=[{"secret": "private-secret"}],
    ))
    result = workflow.start_workflow(check_in())
    assert_failure(result, "NO_SOURCES")
    assert "private-secret" not in json.dumps(result)
    assert not modules.model_calls


def test_a_warning_cannot_be_erased_by_a_saved_same_day_draft(modules):
    workflow.start_workflow(check_in())
    modules.calls.clear()
    result = workflow.start_workflow(check_in(warning_signs=["Radiating pain"]))
    assert_failure(result, "SAFETY_STOP", stopped=True)
    assert modules.calls == ["log"] and len(modules.model_calls) == 1


def test_complete_feedback_retry_after_model_failure_still_reaches_c(modules, monkeypatch):
    modules.records = [history_record()]
    actual = modules.generate_plan
    monkeypatch.setattr(workflow.llm, "generate_plan", lambda *args: make_result(
        "error", error_code="MODEL_ERROR", message="Provider unavailable",
    ))
    current = check_in(previous_completion="Completed")
    assert_failure(workflow.start_workflow(current), "MODEL_ERROR")
    assert modules.records[0]["completion_feedback"]["reported_date"] == current["date"]
    monkeypatch.setattr(workflow.llm, "generate_plan", actual)
    assert workflow.start_workflow(current)["status"] == "awaiting_confirmation"
    assert modules.feedback_calls[0] == modules.feedback_calls[1]
    assert modules.model_calls[0][1]["completion"] == "Completed"


def test_actual_a_adapter_displays_b_draft_and_does_not_generate_on_same_input(modules):
    backend = app.TeamBackend()
    state = {}
    app.handle_action(state, backend, check_in(), "generate")
    app.validate_result(state["current"]["result"])
    assert state["current"]["result"]["status"] == "awaiting_confirmation"
    app.handle_action(state, backend, check_in(), "generate")
    assert len(modules.model_calls) == 1
    assert state["current"]["decision"] is None
