"""Member D feedback-context tests. History records follow INTERFACES.md section 4."""
import json

import pytest

from contracts import check_result
import feedback
import storage
from tests.test_storage import accepted_plan, check_in, draft, feedback_value, final, records

CONTEXT_KEYS = {"previous_plan_id", "previous_actions", "completion", "previous_pain_score",
                "current_pain_score", "previous_fatigue_score", "current_fatigue_score"}


def context(current, history):
    result = check_result(feedback.build_feedback_context(current, history))
    assert result["status"] == "ok", result
    json.dumps(result, allow_nan=False)
    return result["data"]["feedback_context"]


def assert_error(result, code):
    check_result(result)
    assert result["status"] == "error" and result["error_code"] == code


def test_first_use_has_explicit_missing_history():
    value = context(check_in(), [])
    assert set(value) == CONTEXT_KEYS
    assert value == {"previous_plan_id": None, "previous_actions": [], "completion": "Not applicable",
                     "previous_pain_score": None, "current_pain_score": 3,
                     "previous_fatigue_score": None, "current_fatigue_score": 4}


def test_next_day_context_uses_saved_accepted_plan():
    accepted_plan()
    storage.save_feedback("demo-user", "plan-1", feedback_value(pain=2, fatigue=7))
    current = check_in("2026-10-11", previous_completion="Partly completed", pain_score=2, fatigue_score=7)
    value = context(current, records())
    assert value["previous_plan_id"] == "plan-1"
    assert value["previous_actions"] == draft()["plan"]["actions"]
    assert value["completion"] == "Partly completed"
    assert (value["previous_pain_score"], value["current_pain_score"]) == (3, 2)
    assert (value["previous_fatigue_score"], value["current_fatigue_score"]) == (4, 7)


def test_rejected_pending_and_same_day_plans_are_not_previous():
    storage.save_record(draft("rejected", "2026-10-09"))
    storage.save_record(final(draft("rejected", "2026-10-09"), "rejected"))
    storage.save_record(draft("pending", "2026-10-10"))
    accepted_plan("same-day", "2026-10-11")
    assert context(check_in("2026-10-11"), records())["previous_plan_id"] is None


def test_completion_must_match_whether_history_exists():
    assert_error(feedback.build_feedback_context(check_in(previous_completion="Completed"), []),
                 "INVALID_FEEDBACK")
    accepted_plan()
    storage.save_feedback("demo-user", "plan-1", feedback_value())
    assert_error(feedback.build_feedback_context(check_in("2026-10-11"), records()), "INVALID_FEEDBACK")


def test_unsaved_or_mismatched_feedback_is_rejected():
    accepted_plan()
    current = check_in("2026-10-11", previous_completion="Partly completed", pain_score=2, fatigue_score=5)
    assert_error(feedback.build_feedback_context(current, records()), "INVALID_FEEDBACK")
    storage.save_feedback("demo-user", "plan-1", feedback_value())
    assert context(current, records())["previous_plan_id"] == "plan-1"
    current["previous_completion"] = "Completed"
    assert_error(feedback.build_feedback_context(current, records()), "INVALID_FEEDBACK")


def test_history_of_another_user_is_rejected():
    accepted_plan(user="someone-else")
    assert_error(feedback.build_feedback_context(check_in(), records("someone-else")), "INVALID_INPUT")


@pytest.mark.parametrize("current,history", [
    (None, []), ({}, []), (check_in(date="2026-13-01"), []), (check_in(pain_score=True), []),
    (check_in(fatigue_score=11), []), (check_in(previous_completion="Maybe"), []),
    (check_in(), None), (check_in(), [None]),
])
def test_invalid_arguments(current, history):
    assert_error(feedback.build_feedback_context(current, history), "INVALID_INPUT")


def test_context_does_not_share_objects_with_history():
    accepted_plan()
    storage.save_feedback("demo-user", "plan-1", feedback_value())
    history = records()
    value = context(check_in("2026-10-11", previous_completion="Partly completed", pain_score=2,
                             fatigue_score=5), history)
    value["previous_actions"][0]["advice"] = "changed"
    assert history[0]["plan"]["actions"][0]["advice"] != "changed"
