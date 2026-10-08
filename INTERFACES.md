# WorkWell interface contract v1

Keep this file at the repository root and merge it into the `main` branch through a PR so all four members can use it. `main` is a branch name, not a directory to create. This is the first version for team confirmation. When changing fields, enums, or function signatures, update this file and `contracts.py` in the PR and notify affected members.

## 1 Input fields

All values passed between modules must be JSON-serializable. Dates are strings, not Python date objects. Every field below is required. B returns `INVALID_INPUT` for missing fields or incorrect types rather than silently substituting zero. An empty list, a score of zero, and a missing value are distinct. Numbers must be finite; booleans must not be accepted as numbers.

| Field | Type | Range or options |
|---|---|---|
| user_id | str | 1-50 characters after trimming whitespace; fictional users only |
| date | str | Valid calendar date in YYYY-MM-DD format; simulated date |
| sitting_hours | int / float | 0-24; finite number |
| pain_location | str | None, Neck, Shoulders, Lower back, Wrists, Eyes; None is a string |
| pain_score | int | 0-10 |
| fatigue_score | int | 0-10 |
| warning_signs | list[str] | Empty list or options from contracts.WARNING_SIGNS; no duplicates |
| previous_completion | str | Not applicable, Completed, Partly completed, Not completed |

UI constraints do not replace B's server-side checks. When `pain_location == "None"`, pain_score should be zero; otherwise request a correction. Check-in fields are data, not instructions that can change safety rules.

`previous_completion` refers to the latest accepted plan before the current simulated date. D finds that record by user and date. B should indicate which historical plan is being used. If no accepted plan exists, only Not applicable is valid; other options return `INVALID_FEEDBACK`. Multiple submissions on the same day are not used for the next-day feedback demo. The first version does not support arbitrary historical backfilling; use increasing dates to simulate the next day.

## 2 Shared outer result format

All actual cross-module functions return dictionaries with this fixed envelope, constructed using `contracts.make_result`:

```json
{
  "status": "ok",
  "message": "A short, user-safe explanation",
  "error_code": null,
  "data": {},
  "trace": []
}
```

- status: ok (general success), saved (successful write), awaiting_confirmation (human confirmation required), stopped (safety stop), or error (failure).
- message: displayable text without secrets, internal authentication information, or full stack traces.
- error_code: null on success; a non-empty string for stopped/error.
- data: a dictionary containing the function's results; `{}` when empty.
- trace: a list of steps; `[]` when no steps are needed.

Suggested error codes: NOT_IMPLEMENTED, INVALID_INPUT, INVALID_FEEDBACK, SAFETY_STOP, NO_SOURCES, MODEL_ERROR, INVALID_MODEL_OUTPUT, STORAGE_ERROR, and DUPLICATE_CONFLICT.

A safety stop is not a runtime failure. Empty history is a successful empty list, not an error. Retrieval with no matches may return ok with empty sources; B converts this to NO_SOURCES and stops generation. Corrupted files or permission failures must return STORAGE_ERROR, not pretend that history is empty or silently delete files.

## 3 Plan and source formats

Plan:

```json
{
  "plan_id": "server-generated-unique-id",
  "actions": [
    {
      "category": "break",
      "advice": "Action supported by retrieved guidance",
      "reason": "Reason based on current input and feedback",
      "source_ids": ["KB-01"]
    }
  ]
}
```

The program generates plan_id; the model must not generate arbitrary identifiers. actions contains 1-3 items, each with all four fields. category must be break, workstation, screen_rest, or fatigue_management. advice/reason are non-empty strings. source_ids is a non-empty list of identifiers present in this result's sources. B checks the format and allowed categories. B/C must also check whether the content stays within scope and is supported by the sources, rather than checking identifiers alone.

Each source contains id, title, content, and url. The first three are non-empty strings; url links to the actual original source. C maintains approximately 10-15 entries in `data/knowledge.json`. The file is currently empty and the knowledge base is not complete.

## 4 Records, feedback, and audit logs

Record fields: schema_version (integer 1), record_id (equal to plan_id), user_id, date, timestamp (ISO timestamp with timezone), input (original check-in snapshot), plan, sources, plan_status, decision, and completion_feedback.

- Draft: plan_status=awaiting_confirmation, decision=null, completion_feedback=null.
- Accepted: plan_status=accepted, decision=accepted.
- Rejected: plan_status=rejected, decision=rejected; it must not be used as an accepted plan later.
- completion_feedback is initially null. D links subsequent feedback to the previous accepted plan, not to the new draft.
- completion_feedback stores completion, reported_date, pain_score, and fatigue_score. completion is Completed, Partly completed, or Not completed. reported_date must be later than the associated plan date.

D's save_record supports the initial draft save and transitions from draft to accepted/rejected. During transitions, verify that the user, date, check-in, plan, and sources are unchanged. A final decision cannot be reversed. Repeated saves of the same record_id and decision return saved without adding another record. Conflicting decisions return DUPLICATE_CONFLICT.

Audit event fields: event_id (for idempotent writes), timestamp, user_id, record_id (may be null when no plan exists), input, action, source_ids, output, and human_decision (null when no decision exists). Each trace step contains step, status, and tool; add a brief explanation if needed.

## 5 Function signatures and responsibilities

| Owner | Function | Successful status and data |
|---|---|---|
| B | start_workflow(check_in: dict) -> dict | awaiting_confirmation; data={plan, sources}; trace shows actual steps |
| B | submit_decision(record: dict) -> dict | saved; data={record_id} |
| B | validate_input(check_in: dict) -> dict | ok; data={check_in: normalized input} |
| B | check_safety(check_in: dict, history: list[dict]) -> dict | ok; data={}; warning input returns stopped |
| B | validate_plan(plan: dict, sources: list[dict]) -> dict | ok; data={plan} |
| C | retrieve_guidance(check_in: dict) -> dict | ok; data={sources: list} |
| C | generate_plan(check_in: dict, feedback_context: dict, sources: list[dict]) -> dict | ok; data={plan} |
| D | load_history(user_id: str) -> dict | ok; data={records: list}, sorted by date and timestamp from oldest to newest |
| D | load_logs(user_id: str) -> dict | ok; data={events: list} |
| D | save_record(record: dict) -> dict | saved; data={record_id} |
| D | append_log(event: dict) -> dict | saved; data={event_id} |
| D | save_feedback(user_id: str, record_id: str, feedback: dict) -> dict | saved; data={record_id} |
| D | build_feedback_context(check_in: dict, history: list[dict]) -> dict | ok; data={feedback_context: dictionary} |

feedback_context includes at least previous_plan_id (may be null), previous_actions (list), completion, previous_pain_score (may be null), current_pain_score, previous_fatigue_score (may be null), and current_fatigue_score. Represent missing history explicitly with null or empty lists; do not fabricate trends.

start_workflow is the entry point. It coordinates modules and checks every result. Do not call the model after invalid input or a safety stop, and do not generate routine advice without sources. After validating model output, B calls D to save the pending draft and generation log before returning to the UI. Safety stops must also log the actual input, reason, and steps.

submit_decision verifies that the draft exists and matches the UI snapshot, then calls D to save the state and audit event. Return saved only when both the record and decision log are saved. After a partial write, retry using stable record_id/event_id values without duplicate writes or reversed decisions.

Before generating the next day's plan, B/D link and save the completion feedback, then provide it to C through build_feedback_context. If D cannot save, do not ignore the failure and pretend that the workflow completed.

## 6 UI and module boundaries

A's `TeamBackend` converts the shared interface to the internal UI format. Teammates return results according to this file and need not depend on A's internal session_state. app.py does not directly call C's model or replace B's safety rules.

`Offline UI preview` uses the fixture inside app.py. Its return format is only for A's UI tests and matches the internal format produced by adapting actual interfaces. It is not actual retrieval, model generation, or a real safety implementation. Its data is saved in the ignored demo_data directory.

The actual modules are currently placeholders that explicitly report NOT_IMPLEMENTED. Implement them individually before integrating. Passing placeholder tests proves only that placeholder behavior is explicit, not that the entire Agent is complete.
