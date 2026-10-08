"""WorkWell Streamlit interface owned by member A.

Run: python -m streamlit run app.py
Uses a clearly labeled offline UI fixture by default; no model API is called.
See INTERFACES.md in this directory for the team-module interfaces.
"""

import copy
import hashlib
import importlib
import json
import os
import tempfile
import uuid
from datetime import date, datetime
from pathlib import Path

from contracts import ACTION_CATEGORIES, COMPLETION_OPTIONS, PAIN_LOCATIONS, WARNING_SIGNS, check_result


def timestamp():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def fingerprint(check_in):
    """Check whether the current form still matches the displayed plan."""
    text = json.dumps(check_in, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def validate_result(result):
    """Check the result format needed by the UI; member B owns actual safety decisions."""
    if not isinstance(result, dict):
        raise ValueError("Workflow result must be a dictionary.")
    if result.get("status") not in {"awaiting_confirmation", "stopped", "error"}:
        raise ValueError("Unknown workflow status.")
    if not isinstance(result.get("message", ""), str):
        raise ValueError("message must be text.")
    trace = result.get("trace", [])
    if not isinstance(trace, list) or any(not isinstance(x, dict) for x in trace):
        raise ValueError("trace must be a list of dictionaries.")
    if result["status"] != "awaiting_confirmation":
        return
    plan = result.get("plan")
    if not isinstance(plan, dict) or not isinstance(plan.get("plan_id"), str) or not plan["plan_id"]:
        raise ValueError("The plan needs a non-empty plan_id.")
    actions = plan.get("actions")
    if not isinstance(actions, list) or not 1 <= len(actions) <= 3:
        raise ValueError("The plan needs one to three actions.")
    sources = result.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("The plan needs source information.")
    source_ids = set()
    for source in sources:
        if not isinstance(source, dict) or not all(
            isinstance(source.get(k), str) and source[k].strip() for k in ("id", "title", "content")
        ):
            raise ValueError("Invalid source fields.")
        if source["id"] in source_ids:
            raise ValueError("Source IDs must be unique.")
        source_ids.add(source["id"])
    for action in actions:
        if not isinstance(action, dict) or not all(
            isinstance(action.get(k), str) and action[k].strip() for k in ("category", "advice", "reason")
        ):
            raise ValueError("Invalid action fields.")
        if action["category"] not in ACTION_CATEGORIES:
            raise ValueError("Unknown action category.")
        ids = action.get("source_ids")
        if not isinstance(ids, list) or not ids or any(
            not isinstance(x, str) or x not in source_ids for x in ids
        ):
            raise ValueError("Invalid action source IDs.")
    # Reject objects that cannot be saved, rather than failing during confirmation.
    json.dumps(result, ensure_ascii=False, allow_nan=False)


class DemoBackend:
    """Standalone UI fixture for member A; it does not replace the actual B/C/D modules."""

    def __init__(self, path=None):
        self.path = (Path(path) if path else
                     Path(os.environ.get("WORKWELL_DEMO_FILE", str(Path(__file__).resolve().parent / "demo_data" / "ui_demo.json"))))

    def _read(self):
        if not self.path.exists():
            return {"records": [], "logs": []}
        with self.path.open(encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or any(
            not isinstance(data.get(k), list) or any(not isinstance(x, dict) for x in data[k])
            for k in ("records", "logs")
        ):
            raise ValueError("Invalid demo data. Keep a backup before repairing the file.")
        return data

    def _write(self, data):
        # Single-machine, single-user fixture: replace a temporary file to avoid partially written JSON.
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, allow_nan=False)
            os.replace(tmp, self.path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def load_history(self, user_id):
        return [r for r in self._read()["records"] if r.get("user_id") == user_id]

    def load_logs(self, user_id):
        return [r for r in self._read()["logs"] if r.get("user_id") == user_id]

    def start_workflow(self, check_in):
        data = self._read()
        trace = [{"step": "Input check", "status": "completed", "tool": "UI fixture"}]
        if check_in["warning_signs"]:
            result = {
                "status": "stopped",
                "message": "Sample safety stop: warning signs selected. No routine plan is generated. Seek professional assessment.",
                "trace": trace + [{"step": "Safety stop", "status": "stopped", "tool": "UI fixture"}],
            }
        else:
            accepted = [r for r in data["records"] if r.get("user_id") == check_in["user_id"]
                        and r.get("decision") == "accepted"]
            feedback = (f"Previous accepted plan found. Reported completion: {check_in['previous_completion']}."
                        if accepted else "No previously accepted plan found.")
            result = {
                "status": "awaiting_confirmation",
                "message": "Offline UI fixture — no model API or authoritative health retrieval was used.",
                "plan": {"plan_id": str(uuid.uuid4()), "actions": [{
                    "category": "break",
                    "advice": "UI preview: include a brief work break in today's plan.",
                    "reason": feedback + " This is sample text for testing the page.",
                    "source_ids": ["UI-SAMPLE-01"],
                }]},
                "sources": [{"id": "UI-SAMPLE-01", "title": "UI fixture — not a health evidence source",
                             "content": "Placeholder content for checking source display. Replace through member C's module."}],
                "trace": trace + [
                    {"step": "Read history", "status": "completed", "tool": "Sample JSON storage"},
                    {"step": "Prepare sample plan", "status": "completed", "tool": "Offline UI fixture"},
                    {"step": "Human checkpoint", "status": "waiting", "tool": "User confirmation"},
                ],
            }
        data["logs"].append({"timestamp": timestamp(), "user_id": check_in["user_id"],
                             "event": "offline_preview", "input": check_in, "output": result})
        self._write(data)
        return result

    def submit_decision(self, record):
        data = self._read()
        existing = next((r for r in data["records"] if r.get("record_id") == record["record_id"]), None)
        if existing:
            if existing != record:
                raise ValueError("This plan already has a different decision.")
            return {"status": "saved"}  # Retries do not create duplicate records.
        data["records"].append(copy.deepcopy(record))
        data["logs"].append({"timestamp": timestamp(), "user_id": record["user_id"],
                             "event": "human_decision", "record_id": record["record_id"],
                             "decision": record["decision"], "source_ids": [s["id"] for s in record["sources"]]})
        self._write(data)
        return {"status": "saved"}


class TeamBackend:
    """Adapter for team modules: adjust this section if the team interfaces differ."""

    def __init__(self):
        self.workflow = importlib.import_module("workflow")
        self.storage = importlib.import_module("storage")
        for module, names in ((self.workflow, ["start_workflow", "submit_decision"]),
                              (self.storage, ["load_history", "load_logs"])):
            for name in names:
                if not callable(getattr(module, name, None)):
                    raise ValueError(f"Missing function: {module.__name__}.{name}")

    def start_workflow(self, check_in):
        result = check_result(self.workflow.start_workflow(check_in))
        # Map the shared data envelope to the internal UI format; teammates need not use UI internals.
        return {"status": result["status"], "message": result["message"],
                "error_code": result["error_code"], "trace": result["trace"],
                "plan": result["data"].get("plan"), "sources": result["data"].get("sources", [])}

    def submit_decision(self, record):
        return check_result(self.workflow.submit_decision(record))

    def load_history(self, user_id):
        result = check_result(self.storage.load_history(user_id))
        if result["status"] != "ok":
            raise ValueError("History is unavailable.")
        return result["data"]["records"]

    def load_logs(self, user_id):
        result = check_result(self.storage.load_logs(user_id))
        if result["status"] != "ok":
            raise ValueError("Audit log is unavailable.")
        return result["data"]["events"]


def handle_action(state, backend, check_in, action):
    """Separate button handling from rendering for clarity and testing. Return a message level and text."""
    if not check_in["user_id"].strip():
        state.pop("current", None)
        return "error", "Enter a fictional user ID."
    current = state.get("current")
    key = fingerprint(check_in)
    if action == "generate":
        if current and current["fingerprint"] == key and current["result"]["status"] != "error":
            return "info", "This submitted input already has a result. Change an input to create a new plan."
        state.pop("current", None)  # Do not retain a confirmable old draft when new input fails.
        result = backend.start_workflow(copy.deepcopy(check_in))
        validate_result(result)
        state["current"] = {"fingerprint": key, "input": copy.deepcopy(check_in),
                            "result": copy.deepcopy(result), "decision": None}
        return "info", "Workflow finished. Review the result below."
    if action not in {"accepted", "rejected"}:
        raise ValueError("Unknown action.")
    if not current or current["fingerprint"] != key:
        state.pop("current", None)
        return "warning", "The form has changed. Generate a new plan before confirming or rejecting."
    if current["decision"]:
        return "info", "Your decision has already been saved."
    result = current["result"]
    if result["status"] != "awaiting_confirmation":
        return "warning", "There is no plan awaiting confirmation."
    # Allow retries for the same record after a save failure; B/D must save idempotently by record_id.
    record = current.get("pending_record")
    if record is not None and record["decision"] != action:
        return "warning", "A save is pending. Retry the original decision before taking another action."
    if record is None:
        record = {"schema_version": 1, "record_id": result["plan"]["plan_id"], "user_id": check_in["user_id"],
                  "date": check_in["date"], "timestamp": timestamp(), "input": copy.deepcopy(current["input"]),
                  "plan": copy.deepcopy(result["plan"]), "sources": copy.deepcopy(result["sources"]),
                  "decision": action, "plan_status": action, "completion_feedback": None}
        current["pending_record"] = record
    saved = backend.submit_decision(copy.deepcopy(record))
    if not isinstance(saved, dict) or saved.get("status") != "saved":
        raise ValueError("Storage did not confirm that the decision was saved.")
    current["decision"] = action
    return "success", f"Plan {action}. Your decision has been saved."


def main():
    # Import inside main so interface handlers can be tested without Streamlit.
    import streamlit as st

    st.set_page_config(page_title="WorkWell", layout="centered")
    st.title("WorkWell")
    st.write("Daily check-in and work-break planning")
    st.caption("Classroom prototype. Fictional data only. General guidance, not diagnosis or treatment.")
    mode = st.sidebar.radio("Run mode", ["Offline UI preview", "Team modules"])
    if st.session_state.get("backend_mode") != mode:
        st.session_state.pop("current", None)
        st.session_state.pop("notice", None)
        st.session_state["backend_mode"] = mode
    if mode == "Offline UI preview":
        st.info("Offline UI preview: sample text only. No model API is called. This is not the completed agent.")
        backend = DemoBackend()
    else:
        try:
            backend = TeamBackend()
        except Exception:
            st.error("Team modules could not be loaded. Check workflow.py, storage.py and their required functions.")
            st.stop()  # Do not silently switch to sample mode when team-module mode fails.
        st.caption("Team module mode. Unimplemented modules return an explicit error; no sample result is substituted.")

    notice = st.session_state.pop("notice", None)
    if notice:
        getattr(st, notice[0])(notice[1])

    current = st.session_state.get("current")
    can_decide = bool(current and current["result"]["status"] == "awaiting_confirmation"
                      and current["decision"] is None)
    st.subheader("Daily check-in")
    with st.form("check_in", clear_on_submit=False, enter_to_submit=False):
        user_id = st.text_input("Fictional user ID", value="demo-user", max_chars=50)
        simulated_date = st.date_input("Simulated date", value=date.today())
        sitting_hours = st.number_input("Sitting time (hours)", min_value=0.0, max_value=24.0, value=6.0, step=0.5)
        pain_location = st.selectbox("Discomfort area", PAIN_LOCATIONS)
        pain_score = st.slider("Discomfort score", 0, 10, 0)
        fatigue_score = st.slider("Fatigue score", 0, 10, 3)
        warning_signs = st.multiselect("Warning signs", WARNING_SIGNS)
        previous_completion = st.selectbox("Previous accepted plan completion", COMPLETION_OPTIONS)
        st.caption("After changing any input, generate a new plan. Confirmation applies to the submitted snapshot.")
        generate = st.form_submit_button("Generate plan")
        accept = st.form_submit_button("Accept displayed plan", disabled=not can_decide)
        reject = st.form_submit_button("Reject displayed plan", disabled=not can_decide)
    check_in = {"user_id": user_id.strip(), "date": simulated_date.isoformat(),
                "sitting_hours": sitting_hours, "pain_location": pain_location,
                "pain_score": pain_score, "fatigue_score": fatigue_score,
                "warning_signs": sorted(warning_signs), "previous_completion": previous_completion}
    if generate or accept or reject:
        action = "generate" if generate else ("accepted" if accept else "rejected")
        try:
            with st.spinner("Processing..."):
                level, message = handle_action(st.session_state, backend, check_in, action)
            st.session_state["notice"] = (level, message)
        except Exception:
            # Do not expose underlying exceptions that may contain secrets; keep the pending draft for retry.
            st.session_state["notice"] = ("error", "The operation failed. Check module configuration, returned data and storage permissions. No success was confirmed.")
        # Redraw disabled button states; submit buttons are False on rerun, so the model is not called again.
        st.rerun()

    if current:
        result = current["result"]
        st.subheader("Current result")
        status = current["decision"] or result["status"]
        st.write("Status:", status.replace("_", " "))
        if result["status"] == "stopped":
            st.warning(result.get("message", "Workflow stopped."))
        elif result["status"] == "error":
            st.error(result.get("message", "Workflow error."))
        else:
            st.info(result.get("message", "Review the draft plan."))
            for i, item in enumerate(result["plan"]["actions"], 1):
                st.write(f"Action {i} — {item['category']}")
                st.write(item["advice"])
                st.write("Reason:", item["reason"])
                st.write("Sources:", ", ".join(item["source_ids"]))
            with st.expander("Retrieved sources"):
                for source in result["sources"]:
                    st.write(source["id"], "—", source["title"])
                    st.write(source["content"])
                    url = source.get("url", "")
                    if isinstance(url, str) and url.startswith(("https://", "http://")):
                        st.write(url)
        with st.expander("Workflow steps", expanded=True):
            for step in result.get("trace", []):
                st.write(step.get("step", "Step"), "—", step.get("status", ""), "—", step.get("tool", ""))
        with st.expander("Submitted input snapshot"):
            st.json(current["input"])
    else:
        st.info("Submit a check-in to start the workflow.")

    # Viewing history only reads files; it does not generate another plan.
    history_tab, log_tab = st.tabs(["History", "Audit log"])
    with history_tab:
        try:
            history = backend.load_history(check_in["user_id"])
            if not isinstance(history, list):
                raise ValueError("History must be a list.")
            if history:
                st.json(history)
            else:
                st.write("No saved decisions for this fictional user.")
        except Exception:
            st.error("History could not be loaded. Existing files have not been reset.")
    with log_tab:
        try:
            logs = backend.load_logs(check_in["user_id"])
            if not isinstance(logs, list):
                raise ValueError("Logs must be a list.")
            if logs:
                st.json(logs)
            else:
                st.write("No audit events for this fictional user.")
        except Exception:
            st.error("Audit log could not be loaded. Existing files have not been reset.")


if __name__ == "__main__":
    main()
