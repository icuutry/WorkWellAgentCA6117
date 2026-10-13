# WorkWell module and operation guide

WorkWell demonstrates a daily Perceive, Reason and Act loop using fictional check-ins, retrieved guidance, explicit action priorities, human decisions, stored history and feedback. The source tree runs as a Streamlit application; no separate frontend or backend server is required.

## Modules and ownership

| Owner | File | Purpose | Main interface |
|---|---|---|---|
| A | app.py | Collects check-ins, preserves the submitted snapshot, displays priorities, adjustment reasons, execution groups, English sources, history and audit events; handles accept/reject and next-day simulation | TeamBackend, handle_action, main |
| Team | contracts.py | Defines enums, result envelopes, English script checks and approved complementary execution groups | make_result, check_result, execution_groups |
| B | safety.py | Validates input, stops preset warnings, checks action count/schema/priorities, source references, English content, basic scope and supported durations | validate_input, check_safety, validate_plan |
| B | workflow.py | Coordinates all modules, persists pending drafts, reuses an identical saved draft, verifies human decisions and handles partial-save retries | start_workflow, submit_decision |
| C | retrieval.py | Loads fourteen curated English knowledge entries and ranks matches from current discomfort, sitting time, fatigue and completion | load_knowledge, retrieve_guidance |
| C | llm.py | Sends the check-in, saved feedback and retrieved candidates to the selected provider; validates its explicit selections and materializes supported advice | generate_plan, parse_selection, daily_adjustment_note |
| C | data/knowledge.json | English source IDs, titles, summaries, categories, tags, names and original links; one reference-only warning entry is excluded from routine plans | Read by retrieval.py |
| C | data/action_catalog.json | Thirteen bounded English action candidates linked to knowledge IDs; the model cannot replace advice, categories or citations | Read by llm.py |
| D | storage.py | Atomic local JSON writes, user-filtered reads, draft/final decisions, idempotent events, latest accepted plan and completion feedback | load_history, load_previous, save_record, save_feedback, append_log, load_logs |
| D | feedback.py | Builds model context from the latest earlier accepted plan and actual prior/current scores; excludes rejected or pending plans | build_feedback_context |
| D | demo_seed.py | Creates first-use or simulated-history scenarios; backs up existing files before reset | reset_demo_data, command-line entry point |
| Team | tests/ | Unit, integration, Streamlit component and ten independent five-day simulation tests | python -m pytest -q |
| Team | tools/audit_release.py | Checks publishable files for private paths, credential patterns and non-English scripts without exposing secret values | python tools/audit_release.py |
| Team | validate.ps1 | Runs the suite with temporary files inside this managed Windows workspace | PowerShell script |
| Team | .github/workflows/tests.yml | Runs English/credential audit and offline tests on dev pushes and relevant pull requests using Python 3.12 | GitHub Actions |

## Daily lifecycle

1. A collects fictional user ID, simulated date, sitting hours, discomfort area/score, fatigue score, preset warnings and previous accepted plan completion.
2. B validates input and evaluates warning stops before retrieval or model use.
3. D loads stored history. B links today's completion and scores to the latest earlier accepted plan; rejected plans are not previous accepted plans.
4. C retrieves English guidance and offers only its associated action candidates. The model selects one to three distinct action IDs with explicit priorities and three English explanation fields.
5. C sorts explicit priorities and materializes curated advice and citations. Partial completion does not automatically cut the plan to one action. Adjustment notes include actual daily feedback; first use has no invented historical change.
6. B checks the complete plan. Only approved complementary top-priority movement/stretch pairs share an execution arrangement. All underlying actions and sources remain present.
7. D saves the draft and generation audit event. The plan remains awaiting_confirmation until the user explicitly accepts or rejects it.
8. A sends the unchanged submitted plan to B for verification. D saves the final decision and its audit event. A repeat is harmless; an opposite final decision is a conflict.
9. Simulate next day advances only the form date. The next submitted daily check-in supplies new scores and completion; it does not schedule hourly feedback or call the model just by advancing the date.

## Plans and explanations

Every new action contains category, advice, source_ids, priority, reason, priority_reason and adjustment_reason. Priority one is highest. List position does not define rank; duplicate or missing ranks are errors. Plans contain execution_groups, whose priority references cover every action exactly once.

Selection and priority reasons are generated explanations. Advice is constrained to the catalog. Format checks, source IDs and word matching do not prove clinical correctness or complete semantic support. English script checks are a guard, not a universal language classifier; curated source content and sample outputs have been reviewed as English. Human review remains part of the demonstrated workflow.

## Runtime modes

| Interface/configuration | What executes | External model request |
|---|---|---|
| Team modules, WORKWELL_OFFLINE=0 | Full real workflow, retrieval, history, selected model provider, validation and persistence | One request for a new valid check-in; no SDK retries |
| Team modules, WORKWELL_OFFLINE=1 | Full workflow, retrieval and persistence with clearly labelled catalog sample advice | None |
| Offline UI preview | A's independent UI fixture and separate sample storage | None |

Offline mode is deliberate and visible. Live API failure never silently switches to a sample plan. Tests replace the external model boundary; they are not evidence of live provider availability.

## Storage and operation

The fictional user ID is outside the check-in form. Press Enter or leave that field to refresh user-filtered history and audit views without generating a plan. Switching users clears the displayed draft and completion selection. User switching is disabled while a decision save is pending so the same decision remains retryable. Other check-in fields are submitted together as a snapshot.

After confirmation, the result message and human checkpoint reflect the saved decision. History and audit tabs show compact tables of the latest twenty entries, with complete JSON available in collapsed detail panels. Completion feedback is summarized on the earlier accepted record; the underlying stored payloads are unchanged.

runtime_data/records.json stores drafts, decisions and the latest completion feedback. runtime_data/audit_log.json stores generation, failure and human-decision events. WORKWELL_DATA_DIR can select another directory. The UI fixture uses demo_data/. These directories are ignored and are not published.

Use increasing simulated dates. An identical pending check-in can recover a saved draft after a new browser session without a new model call. A day with a final decision cannot be regenerated using a different snapshot. After an uncertain save, restore the submitted inputs and retry the same decision. Corrupt files are reported and preserved.

The prototype supports one local process. Visitors must use distinct fictional IDs to avoid sharing demo histories. The current design does not implement real employee authentication, HR aggregation, per-action completion or autonomous notifications. Local JSON is not guaranteed to persist on Streamlit Community Cloud; see streamlit_deployment.md.

## Configuration and verification

Use the commands in README.md. Runtime packages are in requirements.txt; test packages are in requirements-dev.txt. requirements-lock.txt records the validated development environment. Never publish a private .env or .streamlit/secrets.toml. Only empty configuration templates are tracked.

Run python tools/audit_release.py, then python -m pytest -q. On this managed Windows workspace, validate.ps1 handles the temporary-directory restriction. test_five_day_stress.py runs five consecutive simulated days ten times, using prior provider response shapes with simulated reasons. Tests prohibit external socket connections and HTTP/model requests; Windows event-loop communication over loopback is allowed.
