"""Shared constants and result format. Update INTERFACES.md before changing fields or enums."""

PAIN_LOCATIONS = ["None", "Neck", "Shoulders", "Lower back", "Wrists", "Eyes"]
WARNING_SIGNS = ["Numbness", "Radiating pain", "Severe headache", "Persistent worsening discomfort"]
COMPLETION_OPTIONS = ["Not applicable", "Completed", "Partly completed", "Not completed"]
ACTION_CATEGORIES = {"break", "workstation", "screen_rest", "fatigue_management"}
RESULT_STATUSES = {"ok", "saved", "awaiting_confirmation", "stopped", "error"}


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
