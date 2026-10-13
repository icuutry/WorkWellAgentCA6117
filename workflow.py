"""Member B: deterministic workflow control, with C/D supplied through interfaces.

Generation and explicit human decisions are implemented against the shared contracts.
This module does not import Streamlit, call a provider directly, or write files.
"""

from copy import deepcopy
from datetime import datetime
import json
import uuid

from contracts import check_result, make_result
import feedback
import llm
import retrieval
import safety
import storage


class _Failure(Exception):
    def __init__(self, code, message):
        self.code = code
        self.message = message


def _timestamp():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _snapshot(value):
    return json.loads(json.dumps(value, allow_nan=False))


def _same_json(left, right):
    return json.dumps(left, sort_keys=True, allow_nan=False) == json.dumps(
        right, sort_keys=True, allow_nan=False
    )


def _step(trace, name, status, tool):
    trace.append({"step": name, "status": status, "tool": tool})


def _invoke(function, args, trace, tool, expected, code, message):
    """Check every module envelope and hide exception/provider details."""
    try:
        result = _snapshot(check_result(function(*deepcopy(args))))
        if any(
            not isinstance(item, dict) or any(
                not isinstance(item.get(key), str) for key in ("step", "status", "tool")
            ) for item in result["trace"]
        ):
            raise ValueError("Malformed module trace")
    except Exception:
        _step(trace, tool.split(".")[-1], "error", tool)
        raise _Failure(code, message) from None
    if result["status"] != expected:
        _step(trace, tool.split(".")[-1], "error", tool)
        if result["status"] == "error" and result["error_code"] == "NOT_IMPLEMENTED":
            raise _Failure("NOT_IMPLEMENTED", tool + " is not implemented yet.")
        allowed = {code, "INVALID_MODEL_OUTPUT", "DUPLICATE_CONFLICT"}
        actual = result["error_code"] if result["status"] == "error" else None
        raise _Failure(actual if actual in allowed else code, message)
    _step(trace, tool.split(".")[-1], expected, tool)
    return result["data"]


def _write_log(event, trace):
    data = _invoke(
        storage.append_log, (event,), trace, "storage.append_log", "saved",
        "STORAGE_ERROR", "The audit log could not be saved.",
    )
    if data.get("event_id") != event["event_id"]:
        trace[-1]["status"] = "error"
        raise _Failure("STORAGE_ERROR", "Audit storage did not confirm the expected event ID.")


def _finish_failure(check_in, trace, code, message, *, stopped=False):
    """Log valid submitted inputs; logging failure never lifts a safety stop."""
    status = "stopped" if stopped else "error"
    result = make_result(status, message=message, error_code=code, trace=trace)
    event = {
        "event_id": str(uuid.uuid4()), "timestamp": _timestamp(),
        "user_id": check_in["user_id"], "record_id": None,
        "input": deepcopy(check_in), "action": "workflow_" + status,
        "source_ids": [], "output": deepcopy(result), "human_decision": None,
    }
    try:
        _write_log(event, trace)
    except _Failure as failure:
        result["data"]["logging_error_code"] = failure.code
        result["message"] += " The audit log could not be saved."
    return result


def _is_timestamp(value):
    try:
        parsed = datetime.fromisoformat(value) if isinstance(value, str) else None
        return parsed is not None and parsed.utcoffset() is not None
    except (ValueError, OverflowError):
        return False


def _valid_feedback(value, record):
    if value is None:
        return True
    if record["decision"] != "accepted" or not isinstance(value, dict):
        return False
    if set(value) != {"completion", "reported_date", "pain_score", "fatigue_score"}:
        return False
    probe = deepcopy(record["input"])
    probe.update(date=value["reported_date"], previous_completion=value["completion"])
    return (
        safety.validate_input(probe)["status"] == "ok"
        and value["completion"] != "Not applicable"
        and value["reported_date"] > record["date"]
        and all(type(value[key]) is int and 0 <= value[key] <= 10
                for key in ("pain_score", "fatigue_score"))
    )


def _valid_record(record, user_id):
    required = {
        "schema_version", "record_id", "user_id", "date", "timestamp", "input",
        "plan", "sources", "plan_status", "decision", "completion_feedback",
    }
    if not isinstance(record, dict) or not required <= set(record):
        return False
    if type(record["schema_version"]) is not int or record["schema_version"] != 1:
        return False
    if record["user_id"] != user_id or not _is_timestamp(record["timestamp"]):
        return False
    checked = safety.validate_input(record["input"])
    if checked["status"] != "ok" or not _same_json(checked["data"]["check_in"], record["input"]):
        return False
    if record["input"]["user_id"] != user_id or record["input"]["date"] != record["date"]:
        return False
    if record["input"]["warning_signs"]:
        return False
    if safety.validate_plan(record["plan"], record["sources"])["status"] != "ok":
        return False
    if record["record_id"] != record["plan"]["plan_id"]:
        return False
    if record["plan_status"] == "awaiting_confirmation":
        if record["decision"] is not None or record["completion_feedback"] is not None:
            return False
    elif record["plan_status"] in ("accepted", "rejected"):
        if record["decision"] != record["plan_status"]:
            return False
    else:
        return False
    return _valid_feedback(record["completion_feedback"], record)


def _read_history(user_id, trace):
    data = _invoke(
        storage.load_history, (user_id,), trace, "storage.load_history", "ok",
        "STORAGE_ERROR", "History could not be loaded. Existing data has not been reset.",
    )
    history = data.get("records")
    valid = isinstance(history, list)
    if valid:
        try:
            valid = all(_valid_record(record, user_id) for record in history)
            if valid:
                keys = [(record["date"], datetime.fromisoformat(record["timestamp"]))
                        for record in history]
                ids = [record["record_id"] for record in history]
                valid = keys == sorted(keys) and len(ids) == len(set(ids))
        except (TypeError, ValueError, OverflowError, RecursionError):
            valid = False
    if not valid:
        trace[-1]["status"] = "error"
        raise _Failure("STORAGE_ERROR", "History records are malformed or out of order.")
    return history


def _check_dates(check_in, history):
    if not history:
        return None
    last_date = history[-1]["date"]
    reported_dates = [r["completion_feedback"]["reported_date"] for r in history
                      if r["completion_feedback"] is not None]
    if check_in["date"] < max([last_date] + reported_dates):
        raise _Failure("INVALID_INPUT", "Use an increasing simulated date; historical backfilling is unsupported.")
    if check_in["date"] == last_date:
        same_day = [r for r in history if r["date"] == last_date]
        if (len(same_day) == 1 and same_day[0]["plan_status"] == "awaiting_confirmation"
                and _same_json(same_day[0]["input"], check_in)):
            return same_day[0]
        raise _Failure("INVALID_INPUT", "This simulated day already has a record. Use a later date.")
    return None


def _prepare_feedback(check_in, history, trace):
    accepted = [r for r in history if r["decision"] == "accepted" and r["date"] < check_in["date"]]
    previous = accepted[-1] if accepted else None
    completion = check_in["previous_completion"]
    if previous is None and completion != "Not applicable":
        raise _Failure("INVALID_FEEDBACK", "There is no earlier accepted plan. Select Not applicable.")
    if previous is not None:
        if completion == "Not applicable":
            raise _Failure("INVALID_FEEDBACK", "Report completion for the previous accepted plan.")
        value = {
            "completion": completion, "reported_date": check_in["date"],
            "pain_score": check_in["pain_score"], "fatigue_score": check_in["fatigue_score"],
        }
        stored = previous["completion_feedback"]
        if (stored is not None and stored["reported_date"] == check_in["date"]
                and not _same_json(stored, value)):
            raise _Failure("INVALID_FEEDBACK", "This day's feedback has already been saved with different values.")
        data = _invoke(
            storage.save_feedback, (check_in["user_id"], previous["record_id"], value),
            trace, "storage.save_feedback", "saved", "STORAGE_ERROR",
            "Previous-plan feedback could not be saved; generation stopped.",
        )
        if data.get("record_id") != previous["record_id"]:
            trace[-1]["status"] = "error"
            raise _Failure("STORAGE_ERROR", "Feedback storage did not confirm the previous plan ID.")
        previous["completion_feedback"] = deepcopy(value)
    expected = {
        "previous_plan_id": previous["record_id"] if previous else None,
        "previous_actions": previous["plan"]["actions"] if previous else [],
        "completion": completion,
        "previous_pain_score": previous["input"]["pain_score"] if previous else None,
        "current_pain_score": check_in["pain_score"],
        "previous_fatigue_score": previous["input"]["fatigue_score"] if previous else None,
        "current_fatigue_score": check_in["fatigue_score"],
    }
    data = _invoke(
        feedback.build_feedback_context, (check_in, history), trace,
        "feedback.build_feedback_context", "ok", "INVALID_FEEDBACK",
        "Historical feedback could not be prepared.",
    )
    context = data.get("feedback_context")
    if not isinstance(context, dict) or any(
        key not in context or not _same_json(context[key], value) for key, value in expected.items()
    ):
        trace[-1]["status"] = "error"
        raise _Failure("INVALID_FEEDBACK", "Feedback context does not match the latest accepted plan and current scores.")
    return context


def _retrieve(check_in, trace):
    data = _invoke(
        retrieval.retrieve_guidance, (check_in,), trace, "retrieval.retrieve_guidance", "ok",
        "NO_SOURCES", "Guidance retrieval failed; no routine plan was generated.",
    )
    sources = data.get("sources")
    if isinstance(sources, list) and not sources:
        raise _Failure("NO_SOURCES", "No matching guidance was found; no routine plan was generated.")
    valid = isinstance(sources, list) and all(
        isinstance(source, dict) and all(
            isinstance(source.get(key), str) and source[key].strip()
            for key in ("id", "title", "content", "url")
        ) and safety._valid_source_url(source["url"]) for source in sources
    )
    if valid:
        ids = [source["id"] for source in sources]
        valid = len(ids) == len(set(ids))
    if not valid:
        trace[-1]["status"] = "error"
        raise _Failure("INVALID_MODEL_OUTPUT", "Retrieved sources have invalid fields, URLs or duplicate IDs.")
    return sources


def _generation_steps(record):
    """Canonical successful creation steps; stable across retries of its audit write."""
    steps = []
    for tool, status in (
        ("safety.validate_input", "ok"), ("safety.check_safety", "ok"),
        ("storage.load_history", "ok"),
    ):
        _step(steps, tool.split(".")[-1], status, tool)
    if record["input"]["previous_completion"] != "Not applicable":
        _step(steps, "save_feedback", "saved", "storage.save_feedback")
    for tool, status in (
        ("feedback.build_feedback_context", "ok"), ("retrieval.retrieve_guidance", "ok"),
        ("llm.generate_plan", "ok"), ("safety.validate_plan", "ok"),
        ("storage.save_record", "saved"),
    ):
        _step(steps, tool.split(".")[-1], status, tool)
    return steps


def _draft_event(record):
    return {
        "event_id": "generation:" + record["record_id"], "timestamp": record["timestamp"],
        "user_id": record["user_id"], "record_id": record["record_id"],
        "input": deepcopy(record["input"]), "action": "draft_generated",
        "source_ids": [s["id"] for s in record["sources"]], "human_decision": None,
        "output": {"status": "awaiting_confirmation", "plan": deepcopy(record["plan"]),
                   "sources": deepcopy(record["sources"]), "trace": _generation_steps(record)},
    }


def _return_draft(record, trace):
    _write_log(_draft_event(record), trace)
    _step(trace, "human_confirmation", "waiting", "User confirmation")
    offline = any(action["advice"].startswith("[OFFLINE DEMO]") for action in record["plan"]["actions"])
    return make_result(
        "awaiting_confirmation", data={"plan": deepcopy(record["plan"]), "sources": deepcopy(record["sources"]),
                                       "mode": "offline_demo" if offline else "live"},
        message=("Offline integration demo: no model API was called. " if offline else "")
                + "Draft saved. Review the plan and sources, then explicitly accept or reject it.", trace=trace,
    )


def start_workflow(check_in: dict) -> dict:
    """Validate -> safety -> D memory/feedback -> C sources/model -> draft + audit."""
    trace = []
    checked = safety.validate_input(check_in)
    _step(trace, "validate_input", checked["status"], "safety.validate_input")
    if checked["status"] != "ok":
        checked["trace"] = trace
        return checked
    current = checked["data"]["check_in"]
    safe = safety.check_safety(current, [])
    _step(trace, "check_safety", safe["status"], "safety.check_safety")
    if safe["status"] != "ok":
        return _finish_failure(current, trace, safe["error_code"], safe["message"],
                               stopped=safe["status"] == "stopped")
    try:
        history = _read_history(current["user_id"], trace)
        pending = _check_dates(current, history)
        if pending is not None:
            _step(trace, "reuse_saved_draft", "ok", "workflow.start_workflow")
            return _return_draft(pending, trace)
        context = _prepare_feedback(current, history, trace)
        sources = _retrieve(current, trace)
        data = _invoke(
            llm.generate_plan, (current, context, sources), trace, "llm.generate_plan", "ok",
            "MODEL_ERROR", "Model generation failed; no routine plan was saved.",
        )
        model_plan = data.get("plan")
        if not isinstance(model_plan, dict):
            raise _Failure("INVALID_MODEL_OUTPUT", "The model did not return a plan object.")
        # Accept actions-only C output; replace any provider ID with a program-generated ID.
        plan = deepcopy(model_plan)
        plan["plan_id"] = str(uuid.uuid4())
        checked_plan = safety.validate_plan(plan, sources)
        _step(trace, "validate_plan", checked_plan["status"], "safety.validate_plan")
        if checked_plan["status"] != "ok":
            raise _Failure("INVALID_MODEL_OUTPUT", checked_plan["message"])
        plan = checked_plan["data"]["plan"]
        record = {
            "schema_version": 1, "record_id": plan["plan_id"], "user_id": current["user_id"],
            "date": current["date"], "timestamp": _timestamp(), "input": deepcopy(current),
            "plan": plan, "sources": sources, "plan_status": "awaiting_confirmation",
            "decision": None, "completion_feedback": None,
        }
        saved = _invoke(
            storage.save_record, (record,), trace, "storage.save_record", "saved",
            "STORAGE_ERROR", "The draft could not be saved. No success was confirmed.",
        )
        if saved.get("record_id") != record["record_id"]:
            trace[-1]["status"] = "error"
            raise _Failure("STORAGE_ERROR", "Draft storage did not confirm the expected record ID.")
        return _return_draft(record, trace)
    except _Failure as failure:
        return _finish_failure(current, trace, failure.code, failure.message)


def _check_decision_input(record):
    try:
        submitted = _snapshot(record)
        valid = (
            isinstance(submitted, dict)
            and isinstance(submitted.get("user_id"), str)
            and submitted.get("decision") in ("accepted", "rejected")
            and submitted.get("plan_status") == submitted["decision"]
            and submitted.get("completion_feedback") is None
            and _valid_record(submitted, submitted["user_id"])
        )
    except (TypeError, ValueError, OverflowError, RecursionError):
        valid = False
    if not valid:
        raise _Failure(
            "INVALID_INPUT",
            "Submit an unchanged plan record with an explicit accepted or rejected decision. "
            "Completion feedback is reported through the next check-in.",
        )
    return submitted


def _decision_event(record):
    steps = []
    for tool, name, status in (
        ("workflow.submit_decision", "validate_decision", "ok"),
        ("storage.load_history", "load_history", "ok"),
        ("workflow.submit_decision", "verify_record", "ok"),
        ("storage.save_record", "save_record", "saved"),
    ):
        _step(steps, name, status, tool)
    return {
        "event_id": "decision:" + record["record_id"],
        "timestamp": record["timestamp"], "user_id": record["user_id"],
        "record_id": record["record_id"], "input": deepcopy(record["input"]),
        "action": "human_decision", "source_ids": [source["id"] for source in record["sources"]],
        "human_decision": record["decision"],
        "output": {"status": record["decision"], "record_id": record["record_id"],
                   "plan": deepcopy(record["plan"]), "trace": steps},
    }


def submit_decision(record: dict) -> dict:
    """Verify a persisted draft and save one irreversible decision plus its audit.

    D must provide atomic draft-to-final transitions and idempotent event writes.
    A retry after an uncertain write uses the final record already stored by D.
    """
    trace = []
    try:
        submitted = _check_decision_input(record)
    except _Failure as failure:
        _step(trace, "validate_decision", "error", "workflow.submit_decision")
        return make_result("error", error_code=failure.code, message=failure.message, trace=trace)
    _step(trace, "validate_decision", "ok", "workflow.submit_decision")
    final = None
    try:
        history = _read_history(submitted["user_id"], trace)
        persisted = next((entry for entry in history
                          if entry["record_id"] == submitted["record_id"]), None)
        if persisted is None:
            _step(trace, "verify_record", "error", "workflow.submit_decision")
            raise _Failure("INVALID_INPUT", "The plan has no saved draft. Generate and review a plan first.")
        unchanged = ("schema_version", "record_id", "user_id", "date", "input", "plan", "sources")
        if any(not _same_json(submitted[key], persisted[key]) for key in unchanged):
            _step(trace, "verify_record", "error", "workflow.submit_decision")
            raise _Failure("DUPLICATE_CONFLICT", "The submitted plan no longer matches the saved record.")
        if (persisted["decision"] is not None
                and persisted["decision"] != submitted["decision"]):
            _step(trace, "verify_record", "error", "workflow.submit_decision")
            raise _Failure("DUPLICATE_CONFLICT", "This plan already has a different final decision.")
        _step(trace, "verify_record", "ok", "workflow.submit_decision")

        if persisted["decision"] is None:
            # Build the write from trusted persisted data, not arbitrary UI fields.
            final = deepcopy(persisted)
            final["decision"] = submitted["decision"]
            final["plan_status"] = submitted["decision"]
            final["timestamp"] = _timestamp()  # Program time of the first final transition.
            saved = _invoke(
                storage.save_record, (final,), trace, "storage.save_record", "saved",
                "STORAGE_ERROR", "Decision storage did not confirm the write. Retry the same decision.",
            )
            if saved.get("record_id") != final["record_id"]:
                trace[-1]["status"] = "error"
                raise _Failure("STORAGE_ERROR", "Decision storage did not confirm the expected record ID.")
        else:
            # The final write may have succeeded before its response or audit failed.
            final = deepcopy(persisted)
            _step(trace, "reuse_saved_decision", "ok", "workflow.submit_decision")

        # This body is stable even if the next day has added completion feedback.
        _write_log(_decision_event(final), trace)
        _step(trace, "human_decision", final["decision"], "User confirmation")
        return make_result(
            "saved", data={"record_id": final["record_id"]}, trace=trace,
            message="Plan " + final["decision"] + ". The decision and its audit log are saved.",
        )
    except _Failure as failure:
        message = failure.message
        data = {}
        if final is not None and failure.code in ("STORAGE_ERROR", "NOT_IMPLEMENTED"):
            data = {"record_id": submitted["record_id"], "retry_decision": submitted["decision"]}
            message += " The record may already contain your decision; retry the same decision to finish saving."
        return make_result("error", data=data, error_code=failure.code, message=message, trace=trace)
