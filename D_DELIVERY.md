# Member D integration notes

D supplies storage.py, feedback.py and demo_seed.py. All public functions use the shared result envelope from contracts.py.

## Persistence

`runtime_data/records.json` contains schema_version and records. `runtime_data/audit_log.json` contains schema_version and events. WORKWELL_DATA_DIR can select another directory. Writes use temporary files and atomic replacement. A process lock serializes file writes within one process; multiple writer processes are unsupported.

Missing files are empty history. Corrupt, unreadable or malformed files return STORAGE_ERROR and are preserved. Messages hide filesystem details. Record IDs and event IDs make identical retries idempotent; conflicting writes return DUPLICATE_CONFLICT.

New records must be pending drafts. Only an existing unchanged draft can become accepted or rejected. Final decisions cannot be reversed. Retries preserve the original decision timestamp and saved feedback.

## Memory and feedback

load_history returns this user's records in date/timestamp order. load_previous returns the latest earlier record and latest earlier accepted plan. Rejected plans, pending drafts and same-day/future plans are excluded from the previous accepted plan.

Completion feedback contains completion, reported_date, pain_score and fatigue_score. It belongs to the latest accepted plan before the reported date. Identical retries are harmless; conflicting reports for the same or an earlier date are rejected. The integration permits a later report to update the latest summary when an intervening new plan was rejected. Workflow audit inputs retain earlier reports, and feedback never changes the decision timestamp.

build_feedback_context returns the previous plan ID/actions, completion and previous/current discomfort/fatigue scores. First use has null/empty previous values and requires Not applicable. With an earlier accepted plan, explicit completion and persisted feedback are required. No historical trend is invented.

## Simulated data

Run `python demo_seed.py --list`, `python demo_seed.py first_use` or `python demo_seed.py with_history`. Existing files, including corrupt files, are backed up before reset. History contains a rejected plan on 2026-10-09 and an accepted plan on 2026-10-10. Submit the suggested 2026-10-11 check-in to demonstrate next-day feedback. Seed source IDs K01/K02 belong to the seed fixture, not C's KB identifiers. These records are simulated and must not be presented as real API evidence.

Integration corrected the seed advice to pass B's content/duration checks and resolved the accepted/rejected/third-day feedback conflict. Tests use isolated temporary data and cover persistence, user isolation, decisions, feedback, corrupted files, reset backups and restart behavior. See docs/integration_report.md for current results.
