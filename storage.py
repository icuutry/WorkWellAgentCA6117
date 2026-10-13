"""Member D: actual storage, feedback persistence and audit logs; separate from the offline UI fixture.

Data lives in JSON files under runtime_data/ (override with the WORKWELL_DATA_DIR environment
variable, e.g. to keep a resettable demo scenario apart from saved records):

- records.json   {"schema_version": 1, "records": [...]}  plan records (draft -> accepted/rejected)
- audit_log.json {"schema_version": 1, "events": [...]}   append-only audit events

Every write replaces the file atomically through a temporary file, so a crash never leaves
half-written JSON. A corrupted or unreadable file returns STORAGE_ERROR; it is never treated as
empty history and never overwritten or deleted. Writes are idempotent by record_id / event_id.
Single-machine classroom prototype: a process-wide lock serializes writes from Streamlit
threads; separate processes writing the same directory are not supported.
"""
import copy
import json
import os
import tempfile
import threading
from datetime import date, datetime
from pathlib import Path

from contracts import COMPLETION_OPTIONS, make_result

SCHEMA_VERSION = 1
RECORDS_FILE = "records.json"
LOGS_FILE = "audit_log.json"
RECORD_FIELDS = {"schema_version", "record_id", "user_id", "date", "timestamp", "input", "plan",
                 "sources", "plan_status", "decision", "completion_feedback"}
IMMUTABLE_FIELDS = ("schema_version", "record_id", "user_id", "date", "input", "plan", "sources")
EVENT_FIELDS = {"event_id", "timestamp", "user_id", "record_id", "input", "action", "source_ids",
                "output", "human_decision"}
FEEDBACK_FIELDS = {"completion", "reported_date", "pain_score", "fatigue_score"}
FEEDBACK_COMPLETIONS = [c for c in COMPLETION_OPTIONS if c != "Not applicable"]
STATUS_DECISIONS = {"awaiting_confirmation": None, "accepted": "accepted", "rejected": "rejected"}

_lock = threading.RLock()


class StorageError(Exception):
    """File missing permissions, corrupted, or not in the expected structure."""


class InvalidValue(Exception):
    """A caller passed a value that does not match INTERFACES.md."""


# ---------------------------------------------------------------- file helpers

def data_dir() -> Path:
    configured = os.environ.get("WORKWELL_DATA_DIR")
    return Path(configured) if configured else Path(__file__).resolve().parent / "runtime_data"


def _read(name, key):
    path = data_dir() / name
    try:
        if not path.exists():
            return []
        with path.open(encoding="utf-8") as f:
            content = json.load(f)
    except (OSError, ValueError) as exc:
        raise StorageError(f"{name} cannot be read") from exc
    if (not isinstance(content, dict) or content.get("schema_version") != SCHEMA_VERSION
            or not isinstance(content.get(key), list)
            or any(not isinstance(x, dict) for x in content[key])):
        raise StorageError(f"{name} has an unexpected structure")
    return content[key]


def _write(name, key, items):
    path = data_dir() / name
    body = {"schema_version": SCHEMA_VERSION, key: items}
    tmp = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{name}.", suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(body, f, ensure_ascii=False, indent=2, allow_nan=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        tmp = None
    except (OSError, ValueError) as exc:
        raise StorageError(f"{name} cannot be written") from exc
    finally:
        if tmp is not None and os.path.exists(tmp):
            os.unlink(tmp)


def _storage_error(action):
    # Never expose paths, OS error text or stack traces in user-facing messages.
    return make_result("error", message=f"{action} failed: the data file is unreadable, corrupted "
                       "or not writable. Existing files were left unchanged.", error_code="STORAGE_ERROR")


# ---------------------------------------------------------------- validation helpers

def _json_copy(value, what):
    try:
        return json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise InvalidValue(f"{what} must be JSON-serializable") from exc


def _text(value, what, max_length=None):
    if not isinstance(value, str) or not value.strip():
        raise InvalidValue(f"{what} must be a non-empty string")
    if max_length is not None and len(value.strip()) > max_length:
        raise InvalidValue(f"{what} is too long")
    return value


def _user_id(value):
    _text(value, "user_id", 50)
    return value.strip()


def _date(value, what="date"):
    if not isinstance(value, str) or len(value) != 10:
        raise InvalidValue(f"{what} must use YYYY-MM-DD")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise InvalidValue(f"{what} must be a valid calendar date") from exc


def _timestamp(value, what="timestamp"):
    _text(value, what)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise InvalidValue(f"{what} must be an ISO timestamp") from exc
    if parsed.tzinfo is None:
        raise InvalidValue(f"{what} must include a timezone")


def _score(value, what):
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 10:
        raise InvalidValue(f"{what} must be an integer from 0 to 10")


def _check_feedback(feedback, plan_date=None):
    if not isinstance(feedback, dict) or set(feedback) != FEEDBACK_FIELDS:
        raise InvalidValue("feedback needs exactly completion, reported_date, pain_score and fatigue_score")
    if feedback["completion"] not in FEEDBACK_COMPLETIONS:
        raise InvalidValue("completion must be Completed, Partly completed or Not completed")
    reported = _date(feedback["reported_date"], "reported_date")
    if plan_date is not None and reported <= plan_date:
        raise InvalidValue("reported_date must be later than the plan date")
    _score(feedback["pain_score"], "pain_score")
    _score(feedback["fatigue_score"], "fatigue_score")


def _check_record(record):
    if not isinstance(record, dict) or set(record) != RECORD_FIELDS:
        raise InvalidValue("record must contain exactly the fields listed in INTERFACES.md")
    if isinstance(record["schema_version"], bool) or record["schema_version"] != SCHEMA_VERSION:
        raise InvalidValue("schema_version must be 1")
    _text(record["record_id"], "record_id")
    if record["user_id"] != _user_id(record["user_id"]):
        raise InvalidValue("user_id must already be trimmed")
    plan_date = _date(record["date"])
    _timestamp(record["timestamp"])
    if not isinstance(record["input"], dict):
        raise InvalidValue("input must be the check-in dictionary")
    input_user = record["input"].get("user_id")
    if not isinstance(input_user, str) or input_user.strip() != record["user_id"] \
            or record["input"].get("date") != record["date"]:
        raise InvalidValue("input user_id/date must match the record")
    plan = record["plan"]
    if not isinstance(plan, dict) or plan.get("plan_id") != record["record_id"]:
        raise InvalidValue("plan.plan_id must equal record_id")
    if not isinstance(plan.get("actions"), list) or not 1 <= len(plan["actions"]) <= 3:
        raise InvalidValue("plan needs 1-3 actions")
    sources = record["sources"]
    if not isinstance(sources, list) or not sources or any(
            not isinstance(s, dict) or not isinstance(s.get("id"), str) or not s["id"] for s in sources):
        raise InvalidValue("sources must be a non-empty list of sources with ids")
    status = record["plan_status"]
    if status not in STATUS_DECISIONS or record["decision"] != STATUS_DECISIONS[status]:
        raise InvalidValue("plan_status and decision are inconsistent")
    if record["completion_feedback"] is not None:
        if status != "accepted":
            raise InvalidValue("only accepted plans can carry completion feedback")
        _check_feedback(record["completion_feedback"], plan_date)


def _check_event(event):
    if not isinstance(event, dict) or set(event) != EVENT_FIELDS:
        raise InvalidValue("event must contain exactly the fields listed in INTERFACES.md")
    _text(event["event_id"], "event_id")
    _timestamp(event["timestamp"])
    _user_id(event["user_id"])
    if event["record_id"] is not None:
        _text(event["record_id"], "record_id")
    _text(event["action"], "action")
    if not isinstance(event["source_ids"], list) or any(
            not isinstance(x, str) or not x for x in event["source_ids"]):
        raise InvalidValue("source_ids must be a list of identifiers")
    if event["human_decision"] not in (None, "accepted", "rejected"):
        raise InvalidValue("human_decision must be null, accepted or rejected")


def _invalid(exc, code="INVALID_INPUT"):
    return make_result("error", message=str(exc), error_code=code)


def _sort_key(record):
    return record["date"], record["timestamp"]


def _stored_records():
    records = _read(RECORDS_FILE, "records")
    for record in records:
        try:
            _check_record(record)
        except InvalidValue as exc:
            raise StorageError("records.json contains an invalid record") from exc
    if len({r["record_id"] for r in records}) != len(records):
        raise StorageError("records.json contains duplicate record_id values")
    return records


def _stored_events():
    events = _read(LOGS_FILE, "events")
    for event in events:
        try:
            _check_event(event)
        except InvalidValue as exc:
            raise StorageError("audit_log.json contains an invalid event") from exc
    return events


# ---------------------------------------------------------------- public interface

def load_history(user_id: str) -> dict:
    try:
        user = _user_id(user_id)
    except InvalidValue as exc:
        return _invalid(exc)
    try:
        with _lock:
            records = [r for r in _stored_records() if r["user_id"] == user]
    except StorageError:
        return _storage_error("Loading history")
    records.sort(key=_sort_key)
    return make_result("ok", message=f"{len(records)} record(s) loaded.", data={"records": records},
                       trace=[{"step": "Read history", "status": "completed", "tool": "JSON record store"}])


def load_previous(user_id: str, current_date: str) -> dict:
    """The user's latest record and latest accepted plan dated strictly before current_date.

    Drafts and rejected plans can be the latest record but never the latest accepted plan.
    """
    try:
        user = _user_id(user_id)
        _date(current_date, "current_date")
    except InvalidValue as exc:
        return _invalid(exc)
    result = load_history(user)
    if result["status"] != "ok":
        return result
    earlier = [r for r in result["data"]["records"] if r["date"] < current_date]
    accepted = [r for r in earlier if r["decision"] == "accepted"]
    return make_result("ok", message="Previous records loaded.",
                       data={"latest_record": earlier[-1] if earlier else None,
                             "latest_accepted": accepted[-1] if accepted else None},
                       trace=result["trace"])


def load_logs(user_id: str) -> dict:
    try:
        user = _user_id(user_id)
    except InvalidValue as exc:
        return _invalid(exc)
    try:
        with _lock:
            events = [e for e in _stored_events() if e["user_id"].strip() == user]
    except StorageError:
        return _storage_error("Loading the audit log")
    return make_result("ok", message=f"{len(events)} audit event(s) loaded.", data={"events": events},
                       trace=[{"step": "Read audit log", "status": "completed", "tool": "JSON audit log"}])


def save_record(record: dict) -> dict:
    """Save a new draft, or move a draft to its final decision. Final decisions never change."""
    try:
        record = _json_copy(record, "record")
        _check_record(record)
    except InvalidValue as exc:
        return _invalid(exc)
    record_id = record["record_id"]
    saved = make_result("saved", message="Record saved.", data={"record_id": record_id},
                        trace=[{"step": "Save record", "status": "completed", "tool": "JSON record store"}])
    try:
        with _lock:
            records = _stored_records()
            existing = next((r for r in records if r["record_id"] == record_id), None)
            if existing is None:
                if record["decision"] is not None or record["completion_feedback"] is not None:
                    return _invalid("A new record must be saved as a pending draft before any decision.")
                records.append(record)
                _write(RECORDS_FILE, "records", records)
                return saved
            if any(existing[k] != record[k] for k in IMMUTABLE_FIELDS):
                return make_result("error", message="A record with this ID already exists with different "
                                   "user, date, check-in, plan or sources.", error_code="DUPLICATE_CONFLICT")
            if existing["decision"] is not None:
                if existing["decision"] != record["decision"]:
                    return make_result("error", message="This plan already has a final decision that "
                                       "cannot be changed.", error_code="DUPLICATE_CONFLICT")
                # Retried final decision: keep the stored record (time and saved feedback) unchanged.
                saved["message"] = "Decision was already saved; no duplicate record was added."
                return saved
            if record["decision"] is None:
                if existing != record:
                    return make_result("error", message="A different pending draft with this ID already "
                                       "exists.", error_code="DUPLICATE_CONFLICT")
                saved["message"] = "Draft was already saved; no duplicate record was added."
                return saved
            if record["completion_feedback"] is not None:
                return _invalid("Completion feedback is saved later through save_feedback.")
            records[records.index(existing)] = record
            _write(RECORDS_FILE, "records", records)
            return saved
    except StorageError:
        return _storage_error("Saving the record")


def append_log(event: dict) -> dict:
    """Append an audit event once; retries with the same event_id and body are no-ops."""
    try:
        event = _json_copy(event, "event")
        _check_event(event)
    except InvalidValue as exc:
        return _invalid(exc)
    saved = make_result("saved", message="Audit event saved.", data={"event_id": event["event_id"]},
                        trace=[{"step": "Append audit event", "status": "completed", "tool": "JSON audit log"}])
    try:
        with _lock:
            events = _stored_events()
            existing = next((e for e in events if e["event_id"] == event["event_id"]), None)
            if existing is not None:
                if existing != event:
                    return make_result("error", message="An audit event with this ID already exists with "
                                       "different content.", error_code="DUPLICATE_CONFLICT")
                saved["message"] = "Audit event was already saved; no duplicate was added."
                return saved
            events.append(event)
            _write(LOGS_FILE, "events", events)
            return saved
    except StorageError:
        return _storage_error("Saving the audit event")


def save_feedback(user_id: str, record_id: str, feedback: dict) -> dict:
    """Link next-day completion feedback to the latest accepted plan before reported_date."""
    try:
        user = _user_id(user_id)
        _text(record_id, "record_id")
        feedback = _json_copy(feedback, "feedback")
        _check_feedback(feedback)
    except InvalidValue as exc:
        return _invalid(exc, "INVALID_FEEDBACK")
    try:
        with _lock:
            records = _stored_records()
            record = next((r for r in records if r["record_id"] == record_id), None)
            if record is None or record["user_id"] != user:
                return _invalid("No saved plan with this ID exists for this user.", "INVALID_FEEDBACK")
            if record["decision"] != "accepted":
                return _invalid("Feedback can only be linked to an accepted plan.", "INVALID_FEEDBACK")
            try:
                _check_feedback(feedback, date.fromisoformat(record["date"]))
            except InvalidValue as exc:
                return _invalid(exc, "INVALID_FEEDBACK")
            accepted = [r for r in records if r["user_id"] == user and r["decision"] == "accepted"
                        and r["date"] < feedback["reported_date"]]
            if max(accepted, key=_sort_key)["record_id"] != record_id:
                return _invalid("Feedback must refer to the latest accepted plan before the reported date.",
                                "INVALID_FEEDBACK")
            saved = make_result("saved", message="Completion feedback saved.", data={"record_id": record_id},
                                trace=[{"step": "Link feedback", "status": "completed",
                                        "tool": "JSON record store"}])
            if record["completion_feedback"] is not None:
                stored = record["completion_feedback"]
                if stored == feedback:
                    saved["message"] = "Completion feedback was already saved."
                    return saved
                if feedback["reported_date"] <= stored["reported_date"]:
                    return make_result("error", message="Different completion feedback was already saved "
                                       "for this date or a later date.", error_code="DUPLICATE_CONFLICT")
                # A rejected subsequent plan leaves the older accepted plan as the target.
                # Keep its latest feedback summary; workflow audit inputs retain earlier reports.
            record["completion_feedback"] = feedback  # timestamp of the decision stays unchanged
            _write(RECORDS_FILE, "records", records)
            return saved
    except StorageError:
        return _storage_error("Saving feedback")
