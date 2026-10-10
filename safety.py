"""Member B: input validation and safety rules.

Input validation, preset warning stops, and plan checks are implemented.
See SAFETY_RULES.md and PLAN_VALIDATION.md for the scope and limits.
"""

from datetime import date
from decimal import Decimal
from urllib.parse import urlsplit
import json
import re

from contracts import ACTION_CATEGORIES, COMPLETION_OPTIONS, PAIN_LOCATIONS, WARNING_SIGNS, make_result


def _invalid_input(message: str) -> dict:
    return make_result("error", message=message, error_code="INVALID_INPUT")


def validate_input(check_in: dict) -> dict:
    """Validate the shared input contract and return a separate JSON snapshot.

Warning selections are validated here; check_safety will decide when to stop.
Matching completion feedback to a historical plan belongs to the workflow.
"""
    if not isinstance(check_in, dict):
        return _invalid_input("Check-in must be a dictionary.")

    required_fields = (
        "user_id", "date", "sitting_hours", "pain_location", "pain_score",
        "fatigue_score", "warning_signs", "previous_completion",
    )
    missing_fields = [field for field in required_fields if field not in check_in]
    if missing_fields:
        return _invalid_input("Missing required fields: " + ", ".join(missing_fields) + ".")

    user_id = check_in["user_id"]
    if not isinstance(user_id, str) or not 1 <= len(user_id.strip()) <= 50:
        return _invalid_input("User ID must contain 1-50 characters after trimming whitespace.")

    simulated_date = check_in["date"]
    if not isinstance(simulated_date, str) or re.fullmatch(
        r"[0-9]{4}-[0-9]{2}-[0-9]{2}", simulated_date
    ) is None:
        return _invalid_input("Simulated date must use YYYY-MM-DD format.")
    try:
        date.fromisoformat(simulated_date)
    except ValueError:
        return _invalid_input("Simulated date must be a valid calendar date.")

    sitting_hours = check_in["sitting_hours"]
    # Exact number types reject booleans; the comparison also rejects NaN/infinity.
    if type(sitting_hours) not in (int, float) or not 0 <= sitting_hours <= 24:
        return _invalid_input("Sitting hours must be a finite number between 0 and 24.")

    pain_location = check_in["pain_location"]
    if not isinstance(pain_location, str) or pain_location not in PAIN_LOCATIONS:
        return _invalid_input("Select one of the agreed discomfort areas.")

    for field in ("pain_score", "fatigue_score"):
        value = check_in[field]
        if type(value) is not int or not 0 <= value <= 10:
            return _invalid_input(field + " must be an integer between 0 and 10.")

    if pain_location == "None" and check_in["pain_score"] != 0:
        return _invalid_input("Discomfort score must be zero when the discomfort area is None.")

    warning_signs = check_in["warning_signs"]
    if not isinstance(warning_signs, list) or any(
        not isinstance(sign, str) or sign not in WARNING_SIGNS for sign in warning_signs
    ):
        return _invalid_input("Warning signs must be a list of the agreed warning options.")
    if len(warning_signs) != len(set(warning_signs)):
        return _invalid_input("Warning signs must not contain duplicates.")

    completion = check_in["previous_completion"]
    if not isinstance(completion, str) or completion not in COMPLETION_OPTIONS:
        return _invalid_input("Select one of the agreed previous-plan completion options.")

    try:
        normalized_input = json.loads(json.dumps(check_in, allow_nan=False))
    except (TypeError, ValueError, OverflowError, RecursionError):
        return _invalid_input("All check-in values must be JSON-serializable and finite.")
    normalized_input["user_id"] = user_id.strip()

    return make_result(
        "ok", data={"check_in": normalized_input}, message="Input validation passed."
    )


def check_safety(check_in: dict, history: list[dict]) -> dict:
    """Apply the existing preset warnings before any ordinary plan generation.

    This classroom gate is not a diagnosis or a medical triage system.
    See SAFETY_RULES.md for its basis, limits, and workflow responsibilities.
    """
    input_result = validate_input(check_in)
    trace = [{
        "step": "validate_input", "status": input_result["status"],
        "tool": "safety.validate_input",
    }]
    if input_result["status"] != "ok":
        input_result["trace"] = trace
        return input_result

    warning_signs = input_result["data"]["check_in"]["warning_signs"]
    if warning_signs:
        trace.append({
            "step": "check_safety", "status": "stopped", "tool": "safety.check_safety"
        })
        return make_result(
            "stopped", error_code="SAFETY_STOP", trace=trace,
            message=(
                "Routine work-break advice stopped because of reported warning signs: "
                + "; ".join(warning_signs)
                + ". Please seek professional medical advice."
            ),
        )

    # Current warning stops take priority; history cannot erase a selected warning.
    valid_history = isinstance(history, list) and all(
        isinstance(record, dict) for record in history
    )
    if valid_history:
        try:
            json.dumps(history, allow_nan=False)
        except (TypeError, ValueError, OverflowError, RecursionError):
            valid_history = False
    if not valid_history:
        trace.append({
            "step": "check_safety", "status": "error", "tool": "safety.check_safety"
        })
        return make_result(
            "error", error_code="STORAGE_ERROR", trace=trace,
            message="History data is unavailable or malformed.",
        )

    trace.append({
        "step": "check_safety", "status": "ok", "tool": "safety.check_safety"
    })
    return make_result("ok", message="No preset warning signs selected.", trace=trace)


_ACTION_CUES = {
    "break": {
        "break": r"\b(?:breaks?|pauses?|rest(?:s|ing)?)\b",
        "stand": r"\bstand(?:s|ing)?\b",
        "walk": r"\bwalk(?:s|ing)?\b",
        "move": r"\b(?:mov(?:e|es|ing|ement))\b",
        "stretch": r"\bstretch(?:es|ing)?\b",
    },
    "workstation": {
        "desk": r"\bdesks?\b", "chair": r"\b(?:chairs?|seats?|seating)\b",
        "monitor": r"\b(?:monitors?|screens?|displays?)\b",
        "keyboard": r"\bkeyboards?\b", "mouse": r"\b(?:mouse|mice)\b",
        "wrist": r"\bwrists?\b", "posture": r"\b(?:posture|alignment)\b",
        "height": r"\b(?:height|level)\b", "position": r"\bposition(?:s|ing)?\b",
    },
    "screen_rest": {
        "screen": r"\b(?:screens?|monitors?|displays?)\b",
        "eye": r"\b(?:eyes?|vision)\b", "look": r"\b(?:look(?:s|ing)?|gaze)\b",
        "distance": r"\b(?:distance|distant|far|away)\b",
        "blink": r"\bblink(?:s|ing)?\b", "rest": r"\b(?:rest(?:s|ing)?|breaks?|pauses?)\b",
    },
    "fatigue_management": {
        "rest": r"\b(?:rest(?:s|ing)?|breaks?|pauses?)\b",
        "sleep": r"\bsleep(?:s|ing)?\b", "water": r"\b(?:water|hydrat(?:e|ion))\b",
        "relax": r"\brelax(?:ed|ing|ation)?\b",
        "breathing": r"\b(?:breathe|breathing|breaths?)\b", "stress": r"\bstress\b",
        "pace": r"\b(?:pace|pacing)\b", "fatigue": r"\b(?:fatigue|tired|tiredness)\b",
    },
}

_OUT_OF_SCOPE = re.compile(
    r"\b(?:diagnos\w*|treat(?:ment|ments|ing|ed)?|prescrib\w*|medicat\w*|"
    r"medicines?|dosages?|ibuprofen|paracetamol|acetaminophen|aspirin|"
    r"opioids?|antibiotics?)\b|"
    r"\b(?:you have|this is|you are suffering from)\s+(?:a\s+|an\s+)?"
    r"(?:migraine|carpal tunnel syndrome|radiculopathy|neuropathy|arthritis)\b|"
    r"\b(?:ignore|bypass|disable|override)\b.{0,60}\b(?:safety|warnings?)\b",
    re.IGNORECASE | re.DOTALL,
)
_TIME_DURATION = re.compile(
    r"(?<![\w.])(-?\d+(?:\.\d+)?)\s*(seconds?|secs?|s|minutes?|mins?|hours?|hrs?)\b",
    re.IGNORECASE,
)


def _invalid_plan(message: str) -> dict:
    return make_result(
        "error", message=message, error_code="INVALID_MODEL_OUTPUT",
        trace=[{"step": "validate_plan", "status": "error", "tool": "safety.validate_plan"}],
    )


def _action_cues(category: str, text: str) -> set[str]:
    return {
        cue for cue, pattern in _ACTION_CUES[category].items()
        if re.search(pattern, text, re.IGNORECASE)
    }


def _time_durations(text: str) -> set[Decimal]:
    durations = set()
    for number, unit in _TIME_DURATION.findall(text):
        factor = 60 if unit.lower().startswith("m") else 3600 if unit.lower().startswith("h") else 1
        durations.add(Decimal(number) * factor)
    return durations


def _valid_source_url(url: str) -> bool:
    try:
        parsed = urlsplit(url)
        # Accessing port also checks malformed or out-of-range ports.
        parsed.port
        return (
            parsed.scheme in {"http", "https"} and bool(parsed.hostname)
            and parsed.username is None and parsed.password is None
            and not any(character.isspace() for character in url)
        )
    except ValueError:
        return False


def validate_plan(plan: dict, sources: list[dict]) -> dict:
    """Check the fixed plan schema, actual retrieved references, and basic scope.

    Content cues and duration matches are conservative text checks. They cannot
    prove medical correctness or semantic support; see PLAN_VALIDATION.md.
    The workflow must assign the server-generated plan_id before this call.
    """
    if not isinstance(plan, dict) or set(plan) != {"plan_id", "actions"}:
        return _invalid_plan("Plan must contain exactly plan_id and actions.")
    if not isinstance(plan["plan_id"], str) or not plan["plan_id"].strip():
        return _invalid_plan("Plan must have a non-empty server-assigned plan ID.")
    actions = plan["actions"]
    if not isinstance(actions, list) or not 1 <= len(actions) <= 3:
        return _invalid_plan("Plan must contain between one and three actions.")
    if not isinstance(sources, list) or not sources:
        return _invalid_plan("Plan validation requires the actual retrieved sources.")

    source_by_id = {}
    for source in sources:
        if not isinstance(source, dict) or any(
            not isinstance(source.get(field), str) or not source[field].strip()
            for field in ("id", "title", "content", "url")
        ):
            return _invalid_plan("Each source must have non-empty id, title, content and url fields.")
        if not _valid_source_url(source["url"]):
            return _invalid_plan("Each source URL must be an HTTP or HTTPS address with a host.")
        if source["id"] in source_by_id:
            return _invalid_plan("Retrieved source IDs must be unique.")
        source_by_id[source["id"]] = source

    for action in actions:
        if not isinstance(action, dict) or set(action) != {"category", "advice", "reason", "source_ids"}:
            return _invalid_plan("Each action must contain exactly category, advice, reason and source_ids.")
        category = action["category"]
        if not isinstance(category, str) or category not in ACTION_CATEGORIES:
            return _invalid_plan("Action category is outside the agreed work-break categories.")
        if any(
            not isinstance(action[field], str) or not action[field].strip()
            for field in ("advice", "reason")
        ):
            return _invalid_plan("Action advice and reason must be non-empty strings.")
        source_ids = action["source_ids"]
        if not isinstance(source_ids, list) or not source_ids or any(
            not isinstance(source_id, str) or not source_id.strip() for source_id in source_ids
        ):
            return _invalid_plan("Each action must cite a non-empty list of source IDs.")
        if any(source_id not in source_by_id for source_id in source_ids):
            return _invalid_plan("An action cites a source that was not retrieved for this result.")
        if _OUT_OF_SCOPE.search(action["advice"] + "\n" + action["reason"]):
            return _invalid_plan("Plan text contains an out-of-scope clinical or safety-override statement.")

        advice_cues = _action_cues(category, action["advice"])
        cited_contents = [source_by_id[source_id]["content"] for source_id in source_ids]
        source_cues = set().union(*(_action_cues(category, content) for content in cited_contents))
        if not advice_cues or not advice_cues <= source_cues:
            return _invalid_plan("Action text does not match the basic content cues in its cited guidance.")
        advice_durations = _time_durations(action["advice"])
        source_durations = set().union(*(_time_durations(content) for content in cited_contents))
        if any(duration <= 0 for duration in advice_durations) or not advice_durations <= source_durations:
            return _invalid_plan("Action duration is not supported by its cited guidance.")

    try:
        snapshot = json.loads(json.dumps(plan, allow_nan=False))
        json.dumps(sources, allow_nan=False)
    except (TypeError, ValueError, OverflowError, RecursionError):
        return _invalid_plan("Plan and source values must be JSON-serializable and finite.")
    return make_result(
        "ok", data={"plan": snapshot}, message="Plan format and basic scope checks passed.",
        trace=[{"step": "validate_plan", "status": "ok", "tool": "safety.validate_plan"}],
    )

