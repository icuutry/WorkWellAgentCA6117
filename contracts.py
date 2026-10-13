"""Shared constants and result format. Update INTERFACES.md before changing fields or enums."""

PAIN_LOCATIONS = ["None", "Neck", "Shoulders", "Lower back", "Wrists", "Eyes"]
WARNING_SIGNS = ["Numbness", "Radiating pain", "Severe headache", "Persistent worsening discomfort"]
COMPLETION_OPTIONS = ["Not applicable", "Completed", "Partly completed", "Not completed"]
ACTION_CATEGORIES = {"break", "workstation", "screen_rest", "fatigue_management"}
RESULT_STATUSES = {"ok", "saved", "awaiting_confirmation", "stopped", "error"}
ACTION_DETAIL_FIELDS = {"priority", "priority_reason", "adjustment_reason"}
MERGEABLE_SOURCE_PAIRS = {frozenset({"KB-02", "KB-07"}), frozenset({"KB-01", "KB-07"})}


def is_english_content(value):
    """Script check for curated English content; not a full language classifier."""
    return (isinstance(value, str) and bool(value.strip())
            and any("a" <= c.lower() <= "z" for c in value)
            and not any(c.isalpha() and not c.isascii() for c in value))


def execution_groups(actions):
    """Group complementary top priorities while retaining every original action."""
    ordered = sorted(actions, key=lambda action: action["priority"])
    groups = []
    merged = False
    if len(ordered) >= 2:
        first, second = ordered[:2]
        ids = set(first["source_ids"] + second["source_ids"])
        merged = (first["category"] == second["category"] == "break"
                  and len(first["source_ids"]) == len(second["source_ids"]) == 1
                  and frozenset(ids) in MERGEABLE_SOURCE_PAIRS)
        if merged:
            groups.append({"group_id": "group-1", "action_priorities": [1, 2],
                           "title": "Combined priority work break",
                           "merge_reason": "A movement break and gentle neck/shoulder stretches can share one work break. Both actions and their separate sources are retained."})
    for action in ordered[2:] if merged else ordered:
        groups.append({"group_id": f"group-{len(groups) + 1}",
                       "action_priorities": [action["priority"]],
                       "title": "Separate supported action",
                       "merge_reason": "Keep this action separate; no approved complementary pair applies."})
    return groups


def make_result(status, *, data=None, message="", error_code=None, trace=None):
    if status not in RESULT_STATUSES:
        raise ValueError("Unknown result status")
    if status in {"stopped", "error"} and not error_code:
        raise ValueError("Stopped/error results require an error_code")
    return {"status": status, "message": message, "error_code": error_code,
            "data": {} if data is None else data, "trace": [] if trace is None else trace}


def check_result(result):
    """Validate the common outer envelope; this does not perform medical assessment."""
    if not isinstance(result, dict) or result.get("status") not in RESULT_STATUSES:
        raise ValueError("Invalid status envelope")
    if not isinstance(result.get("data"), dict) or not isinstance(result.get("message"), str):
        raise ValueError("Invalid data/message envelope")
    if not isinstance(result.get("trace"), list):
        raise ValueError("Invalid trace envelope")
    if result["status"] in {"stopped", "error"} and not isinstance(result.get("error_code"), str):
        raise ValueError("Missing error_code")
    if result["status"] in {"stopped", "error"} and not result["error_code"]:
        raise ValueError("Empty error_code")
    if result["status"] not in {"stopped", "error"} and result.get("error_code") is not None:
        raise ValueError("Successful results must not contain error_code")
    return result
