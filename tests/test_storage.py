"""Member D storage tests: real JSON files in a per-test temporary directory (see conftest.py)."""
from copy import deepcopy
import json

import pytest

import app
from contracts import check_result
import storage


def check_in(day="2026-10-10", user="demo-user", **changes):
    value = {"user_id": user, "date": day, "sitting_hours": 6.0, "pain_location": "Neck",
             "pain_score": 3, "fatigue_score": 4, "warning_signs": [],
             "previous_completion": "Not applicable"}
    value.update(changes)
    return value


def draft(record_id="plan-1", day="2026-10-10", user="demo-user", **changes):
    value = {
        "schema_version": 1, "record_id": record_id, "user_id": user, "date": day,
        "timestamp": day + "T09:00:00+08:00", "input": check_in(day, user),
        "plan": {"plan_id": record_id, "actions": [{
            "category": "break", "advice": "Take a short walking break every hour.",
            "reason": "Six hours of sitting reported.", "source_ids": ["KB-01"]}]},
        "sources": [{"id": "KB-01", "title": "Breaks", "content": "Stand up regularly.",
                     "url": "https://example.org/breaks"}],
        "plan_status": "awaiting_confirmation", "decision": None, "completion_feedback": None,
    }
    value.update(changes)
    return value


def final(record, decision, timestamp=None):
    value = deepcopy(record)
    value.update(plan_status=decision, decision=decision)
    if timestamp:
        value["timestamp"] = timestamp
    return value


def event(event_id="generation:plan-1", **changes):
    value = {"event_id": event_id, "timestamp": "2026-10-10T09:00:00+08:00", "user_id": "demo-user",
             "record_id": "plan-1", "input": check_in(), "action": "generate_plan",
             "source_ids": ["KB-01"], "output": {"status": "awaiting_confirmation", "trace": []},
             "human_decision": None}
    value.update(changes)
    return value


def feedback_value(day="2026-10-11", completion="Partly completed", pain=2, fatigue=5):
    return {"completion": completion, "reported_date": day, "pain_score": pain, "fatigue_score": fatigue}


def records(user="demo-user"):
    result = check_result(storage.load_history(user))
    assert result["status"] == "ok"
    return result["data"]["records"]


def assert_error(result, code):
    check_result(result)
    assert result["status"] == "error" and result["error_code"] == code
    json.dumps(result, allow_nan=False)


# ----------------------------------------------------------------- history and records

def test_empty_history_and_logs_are_ok_and_create_no_files(isolated_runtime_data):
    assert records() == []
    assert check_result(storage.load_logs("demo-user"))["data"] == {"events": []}
    assert not isolated_runtime_data.exists()


def test_draft_then_accept_persists_on_disk(isolated_runtime_data):
    result = check_result(storage.save_record(draft()))
    assert result["status"] == "saved" and result["data"] == {"record_id": "plan-1"}
    accepted = final(draft(), "accepted", "2026-10-10T09:05:00+08:00")
    assert storage.save_record(accepted)["status"] == "saved"
    assert records() == [accepted]
    on_disk = json.loads((isolated_runtime_data / "records.json").read_text(encoding="utf-8"))
    assert on_disk == {"schema_version": 1, "records": [accepted]}


def test_history_is_per_user_and_sorted_oldest_first():
    storage.save_record(draft("p3", "2026-10-12"))
    storage.save_record(draft("p1", "2026-10-10"))
    storage.save_record(draft("other", "2026-10-11", user="someone-else"))
    storage.save_record(draft("p2", "2026-10-10", timestamp="2026-10-10T10:00:00+08:00"))
    assert [r["record_id"] for r in records()] == ["p1", "p2", "p3"]
    assert [r["record_id"] for r in records("someone-else")] == ["other"]
    assert [r["record_id"] for r in records("  demo-user  ")] == ["p1", "p2", "p3"]


def test_identical_draft_and_decision_retries_do_not_duplicate():
    storage.save_record(draft())
    assert storage.save_record(draft())["status"] == "saved"
    accepted = final(draft(), "accepted")
    storage.save_record(accepted)
    storage.save_feedback("demo-user", "plan-1", feedback_value())
    retry = final(draft(), "accepted", "2026-10-10T23:00:00+08:00")
    assert storage.save_record(retry)["status"] == "saved"
    [saved] = records()
    assert saved["timestamp"] == accepted["timestamp"]  # first decision time is kept
    assert saved["completion_feedback"] == feedback_value()  # retry does not erase feedback


def test_final_decision_cannot_be_reversed_or_reset_to_draft():
    storage.save_record(draft())
    storage.save_record(final(draft(), "rejected"))
    assert_error(storage.save_record(final(draft(), "accepted")), "DUPLICATE_CONFLICT")
    assert_error(storage.save_record(draft()), "DUPLICATE_CONFLICT")
    assert records()[0]["decision"] == "rejected"


@pytest.mark.parametrize("field,value", [
    ("input", check_in(pain_score=9)), ("sources", [{"id": "KB-99", "title": "x", "content": "y", "url": ""}]),
    ("plan", {"plan_id": "plan-1", "actions": [{"category": "workstation", "advice": "a", "reason": "b",
                                                 "source_ids": ["KB-01"]}]}),
])
def test_changed_immutable_content_is_a_conflict(field, value):
    storage.save_record(draft())
    changed = final(draft(), "accepted")
    changed[field] = value
    assert_error(storage.save_record(changed), "DUPLICATE_CONFLICT")
    assert records() == [draft()]


def test_different_draft_with_same_id_is_a_conflict():
    storage.save_record(draft())
    assert_error(storage.save_record(draft(timestamp="2026-10-10T11:00:00+08:00")), "DUPLICATE_CONFLICT")


def test_new_record_must_start_as_draft():
    assert_error(storage.save_record(final(draft(), "accepted")), "INVALID_INPUT")
    assert records() == []


@pytest.mark.parametrize("bad", [
    None, [], {}, draft(extra="field"), draft(schema_version=2), draft(schema_version=True),
    draft(record_id=""), draft(user_id=" demo-user"), draft(user_id="x" * 51), draft(date="2026-02-30"),
    draft(date="10/10/2026"), draft(timestamp="2026-10-10T09:00:00"), draft(timestamp="yesterday"),
    draft(plan={"plan_id": "other", "actions": []}), draft(sources=[]),
    draft(plan_status="accepted", decision=None), draft(plan_status="awaiting_confirmation", decision="accepted"),
    draft(completion_feedback=feedback_value()), draft(input=check_in(user="someone-else")),
    draft(input={**check_in(), "sitting_hours": float("inf")}),
    draft(input={**check_in(), "bad": object()}),
])
def test_invalid_records_are_rejected_without_writing(bad, isolated_runtime_data):
    assert_error(storage.save_record(bad), "INVALID_INPUT")
    assert not isolated_runtime_data.exists()


def test_caller_mutation_after_save_does_not_change_stored_record():
    value = draft()
    storage.save_record(value)
    value["plan"]["actions"][0]["advice"] = "changed"
    assert records()[0]["plan"]["actions"][0]["advice"] == "Take a short walking break every hour."


# ----------------------------------------------------------------- audit log

def test_audit_events_are_idempotent_by_event_id():
    assert check_result(storage.append_log(event()))["data"] == {"event_id": "generation:plan-1"}
    assert storage.append_log(event())["status"] == "saved"
    assert_error(storage.append_log(event(action="something else")), "DUPLICATE_CONFLICT")
    storage.append_log(event("decision:plan-1", action="human_decision", human_decision="accepted"))
    storage.append_log(event("stop-1", user_id="someone-else", record_id=None, source_ids=[]))
    logs = check_result(storage.load_logs("demo-user"))["data"]["events"]
    assert [e["event_id"] for e in logs] == ["generation:plan-1", "decision:plan-1"]


@pytest.mark.parametrize("bad", [
    {}, event(event_id=""), event(timestamp="2026-10-10"), event(user_id=""), event(record_id=""),
    event(action=""), event(source_ids="KB-01"), event(source_ids=[1]), event(human_decision="maybe"),
    event(extra=True), event(output={"value": float("nan")}),
])
def test_invalid_events_are_rejected(bad):
    assert_error(storage.append_log(bad), "INVALID_INPUT")


# ----------------------------------------------------------------- feedback

def accepted_plan(record_id="plan-1", day="2026-10-10", user="demo-user"):
    storage.save_record(draft(record_id, day, user))
    storage.save_record(final(draft(record_id, day, user), "accepted"))


def test_feedback_links_to_previous_accepted_plan_and_is_idempotent():
    accepted_plan()
    result = check_result(storage.save_feedback("demo-user", "plan-1", feedback_value()))
    assert result["status"] == "saved" and result["data"] == {"record_id": "plan-1"}
    assert storage.save_feedback("demo-user", "plan-1", feedback_value())["status"] == "saved"
    assert_error(storage.save_feedback("demo-user", "plan-1", feedback_value(completion="Completed")),
                 "DUPLICATE_CONFLICT")
    [saved] = records()
    assert saved["completion_feedback"] == feedback_value()
    assert saved["timestamp"] == draft()["timestamp"]


def test_feedback_rejects_rejected_draft_missing_or_foreign_plans():
    storage.save_record(draft("pending"))
    storage.save_record(draft("rejected", "2026-10-09"))
    storage.save_record(final(draft("rejected", "2026-10-09"), "rejected"))
    accepted_plan("foreign", user="someone-else")
    for record_id in ("pending", "rejected", "missing", "foreign"):
        assert_error(storage.save_feedback("demo-user", record_id, feedback_value()), "INVALID_FEEDBACK")


def test_feedback_must_target_latest_accepted_plan_before_reported_date():
    accepted_plan("old", "2026-10-08")
    accepted_plan("new", "2026-10-10")
    assert_error(storage.save_feedback("demo-user", "old", feedback_value("2026-10-11")), "INVALID_FEEDBACK")
    assert storage.save_feedback("demo-user", "old", feedback_value("2026-10-09"))["status"] == "saved"
    assert storage.save_feedback("demo-user", "new", feedback_value("2026-10-11"))["status"] == "saved"


@pytest.mark.parametrize("bad", [
    {}, feedback_value(completion="Not applicable"), feedback_value(day="2026-10-10"),
    feedback_value(day="2026-10-09"), feedback_value(day="tomorrow"), feedback_value(pain=11),
    feedback_value(fatigue=True), feedback_value(pain=2.5), {**feedback_value(), "note": "x"},
])
def test_invalid_feedback_is_rejected(bad):
    accepted_plan()
    assert_error(storage.save_feedback("demo-user", "plan-1", bad), "INVALID_FEEDBACK")
    assert records()[0]["completion_feedback"] is None


# ----------------------------------------------------------------- corrupted files

@pytest.mark.parametrize("content", ["{not json", "[]", '{"schema_version": 1, "records": {}}',
                                     '{"schema_version": 1, "records": [{"record_id": "x"}]}',
                                     '{"records": []}'])
def test_corrupted_records_file_is_a_storage_error_and_never_overwritten(isolated_runtime_data, content):
    isolated_runtime_data.mkdir(parents=True)
    path = isolated_runtime_data / "records.json"
    path.write_text(content, encoding="utf-8")
    assert_error(storage.load_history("demo-user"), "STORAGE_ERROR")
    assert_error(storage.save_record(draft()), "STORAGE_ERROR")
    assert_error(storage.save_feedback("demo-user", "plan-1", feedback_value()), "STORAGE_ERROR")
    assert path.read_text(encoding="utf-8") == content


def test_corrupted_log_file_is_a_storage_error(isolated_runtime_data):
    isolated_runtime_data.mkdir(parents=True)
    (isolated_runtime_data / "audit_log.json").write_text("garbage", encoding="utf-8")
    assert_error(storage.load_logs("demo-user"), "STORAGE_ERROR")
    assert_error(storage.append_log(event()), "STORAGE_ERROR")


def test_write_failure_is_reported_without_leaking_details(monkeypatch, isolated_runtime_data):
    def broken(*args, **kwargs):
        raise PermissionError("/secret/path denied")
    monkeypatch.setattr(storage.os, "replace", broken)
    result = storage.save_record(draft())
    assert_error(result, "STORAGE_ERROR")
    assert "/secret/path" not in json.dumps(result)
    assert not any(isolated_runtime_data.glob("*.tmp")) and not any(isolated_runtime_data.glob(".*.tmp"))
    monkeypatch.undo()
    assert storage.save_record(draft())["status"] == "saved"  # a retry with the same ID succeeds


def test_invalid_user_id_queries():
    for bad in ("", "   ", None, 5, "x" * 51):
        assert_error(storage.load_history(bad), "INVALID_INPUT")
        assert_error(storage.load_logs(bad), "INVALID_INPUT")


# ----------------------------------------------------------------- previous records and restart

def test_load_previous_distinguishes_drafts_rejected_and_accepted():
    accepted_plan("accepted", "2026-10-08")
    storage.save_record(draft("rejected", "2026-10-09"))
    storage.save_record(final(draft("rejected", "2026-10-09"), "rejected"))
    storage.save_record(draft("pending", "2026-10-10"))
    accepted_plan("today", "2026-10-11")
    data = check_result(storage.load_previous("demo-user", "2026-10-11"))["data"]
    assert data["latest_record"]["record_id"] == "pending"
    assert data["latest_accepted"]["record_id"] == "accepted"
    empty = check_result(storage.load_previous("demo-user", "2026-10-01"))["data"]
    assert empty == {"latest_record": None, "latest_accepted": None}
    assert_error(storage.load_previous("demo-user", "not-a-date"), "INVALID_INPUT")


def test_records_survive_a_program_restart():
    import importlib
    accepted_plan()
    storage.append_log(event())
    reloaded = importlib.reload(storage)
    assert [r["record_id"] for r in records()] == ["plan-1"]
    assert len(check_result(reloaded.load_logs("demo-user"))["data"]["events"]) == 1


# ----------------------------------------------------------------- A's adapter

def test_team_backend_reads_history_and_logs_from_real_storage():
    accepted_plan()
    storage.append_log(event())
    backend = app.TeamBackend()
    assert [r["record_id"] for r in backend.load_history("demo-user")] == ["plan-1"]
    assert [e["event_id"] for e in backend.load_logs("demo-user")] == ["generation:plan-1"]
