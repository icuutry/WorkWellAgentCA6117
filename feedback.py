"""Member D: turn history and current completion feedback into model context.

The context is built only from saved records and the current check-in. Missing history is
represented explicitly with null / empty values; no trend is invented. Rejected plans and plans
dated on or after the current check-in are never used as the "previous" plan.
"""
import copy
from datetime import date

from contracts import COMPLETION_OPTIONS, make_result


def _invalid(message, code="INVALID_INPUT"):
    return make_result("error", message=message, error_code=code)


def _valid_date(value):
    if not isinstance(value, str) or len(value) != 10:
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _score(value):
    return not isinstance(value, bool) and isinstance(value, int) and 0 <= value <= 10


def find_previous_accepted(user_id: str, current_date: str, history: list[dict]):
    """Latest accepted plan of this user dated strictly before current_date, or None."""
    accepted = [r for r in history if r.get("user_id") == user_id and r.get("decision") == "accepted"
                and isinstance(r.get("date"), str) and r["date"] < current_date]
    if not accepted:
        return None
    return max(accepted, key=lambda r: (r["date"], str(r.get("timestamp", ""))))


def build_feedback_context(check_in: dict, history: list[dict]) -> dict:
    if not isinstance(check_in, dict):
        return _invalid("check_in must be a dictionary.")
    user_id = check_in.get("user_id")
    if not isinstance(user_id, str) or not user_id.strip():
        return _invalid("check_in.user_id is required.")
    user_id = user_id.strip()
    if not _valid_date(check_in.get("date")):
        return _invalid("check_in.date must be a valid YYYY-MM-DD date.")
    if not _score(check_in.get("pain_score")) or not _score(check_in.get("fatigue_score")):
        return _invalid("check_in pain_score and fatigue_score must be integers from 0 to 10.")
    completion = check_in.get("previous_completion")
    if completion not in COMPLETION_OPTIONS:
        return _invalid("check_in.previous_completion is not a valid option.")
    if not isinstance(history, list) or any(not isinstance(r, dict) for r in history):
        return _invalid("history must be a list of records.")
    if any(r.get("user_id") != user_id for r in history):
        return _invalid("history contains another user's records.")

    previous = find_previous_accepted(user_id, check_in["date"], history)
    trace = [{"step": "Build feedback context", "status": "completed", "tool": "Feedback builder",
              "detail": f"previous accepted plan: {previous['record_id'] if previous else 'none'}"}]
    if previous is None:
        if completion != "Not applicable":
            return _invalid("No earlier accepted plan exists, so previous completion must be "
                            "Not applicable.", "INVALID_FEEDBACK")
        context = {
            "previous_plan_id": None, "previous_actions": [], "completion": completion,
            "previous_pain_score": None, "current_pain_score": check_in["pain_score"],
            "previous_fatigue_score": None, "current_fatigue_score": check_in["fatigue_score"],
        }
        return make_result("ok", message="No earlier accepted plan; first-use context.",
                           data={"feedback_context": context}, trace=trace)

    if completion == "Not applicable":
        return _invalid("An earlier accepted plan exists; report whether it was completed.",
                        "INVALID_FEEDBACK")
    saved = previous.get("completion_feedback")
    if not isinstance(saved, dict):
        return _invalid("Completion feedback for the previous accepted plan has not been saved yet.",
                        "INVALID_FEEDBACK")
    if saved.get("reported_date") == check_in["date"] and (
            saved.get("completion") != completion or saved.get("pain_score") != check_in["pain_score"]
            or saved.get("fatigue_score") != check_in["fatigue_score"]):
        return _invalid("Saved completion feedback does not match the current check-in.", "INVALID_FEEDBACK")

    previous_input = previous.get("input") if isinstance(previous.get("input"), dict) else {}
    plan = previous.get("plan") if isinstance(previous.get("plan"), dict) else {}
    context = {
        "previous_plan_id": previous["record_id"],
        "previous_actions": copy.deepcopy(plan.get("actions", [])),
        "completion": completion,
        "previous_pain_score": previous_input.get("pain_score"),
        "current_pain_score": check_in["pain_score"],
        "previous_fatigue_score": previous_input.get("fatigue_score"),
        "current_fatigue_score": check_in["fatigue_score"],
    }
    return make_result("ok", message="Context built from the previous accepted plan.",
                       data={"feedback_context": context}, trace=trace)
