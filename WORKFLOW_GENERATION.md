# B workflow generation and decisions

`start_workflow(check_in)` is implemented using the signatures in INTERFACES.md.
`submit_decision(record)` is also implemented; see B_DELIVERY.md for decision and retry behavior.
No dependency or Python version change is needed.

## Call sequence

1. Validate and copy the check-in. Invalid input returns INVALID_INPUT without calling other modules.
2. Apply the four shared warning rules. A warning stops routine suggestions before history, retrieval or model calls. Attempt to log the stop through D.
3. Load and check D's history, including user isolation, ordering, record states and unchanged input/plan identifiers. Malformed history returns STORAGE_ERROR; it is never replaced with empty history.
4. Use increasing simulated dates. An identical saved pending draft for the latest date can resume without calling the model or saving a second record. Other same-day submissions and backfilling are rejected.
5. Find the latest earlier accepted plan; rejected plans are excluded. Require its completion report, save it to that old plan, then pass the updated history to D's feedback builder. With no accepted plan, require Not applicable and explicit missing-history values. Check that D's context agrees with the real records and current scores.
6. Ask C for guidance. No matches returns NO_SOURCES. Malformed references stop before a model call.
7. Pass the check-in, checked feedback context and retrieved sources to C's model function. Give each module independent copies. Provider errors, malformed results and out-of-scope plans stop generation.
8. Assign a new UUID in the program and check the plan through safety.validate_plan. C may return actions only or a plan with an ID; a provider-supplied ID is replaced. Extra fields and invalid actions are still rejected.
9. Save a pending draft through D. Its decision and completion_feedback are null. Save its generation audit event, then return awaiting_confirmation to A. Both writes must confirm the correct IDs.

No plan is automatically accepted. submit_decision requires an explicit accepted or rejected decision that matches the persisted draft.

## Failure and retry behavior

Valid submitted inputs that fail are logged with their reason and actual reached steps. Raw exceptions and provider error text are not displayed or copied into logs. Invalid input may contain unserializable objects and is returned before logging.

A safety stop keeps status=stopped and error_code=SAFETY_STOP even if D's audit operation fails. In that case the message reports the failed log write and data.logging_error_code reports STORAGE_ERROR or NOT_IMPLEMENTED. The model is never resumed. Other failures keep their primary error code and also report failed logging when applicable.

The generation event ID is `generation:<record_id>`. Its timestamp and successful creation steps derive from the persisted draft, so retrying an uncertain audit write uses the identical event body. Its trace describes creation of that draft; the result returned on a retry separately shows the actual history read and draft reuse. D must enforce event_id idempotency. If a draft write succeeded but its response or subsequent log write failed, a retry reads that draft and repairs the audit without a second model call.

Only the single-user classroom flow is supported. Two simultaneous generation requests from separate sessions are not made atomic by this module; a future concurrent system needs a D-side lock or atomic claim. A's existing session state prevents repeated clicks within one session.

## Validation and remaining integration

tests/test_workflow_generation.py uses clearly labelled synthetic in-memory C/D doubles. It exercises success, warnings, no sources, invalid plans, dependency failures, prior accepted/rejected history, saved feedback, malformed history, draft reuse, partial writes and A's actual adapter. It makes no network call and writes no project data.

C's real retrieval/API and D's real persistence are still their owners' responsibility. Team modules will explicitly report NOT_IMPLEMENTED until those functions are implemented. These tests verify B's control flow and boundaries, not a completed four-member demo or a real model call. Full disk persistence and real API integration must be checked later with the completed C/D modules.

The safety and grounding limits remain those in SAFETY_RULES.md and PLAN_VALIDATION.md. History and draft rechecks use the current B plan validator; incompatible old demo records require explicit repair or a deliberate demo reset by D, not silent deletion by B.
