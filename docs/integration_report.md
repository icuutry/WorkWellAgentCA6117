# WorkWell integration report

Date: 2026-10-13. Work was performed in the separate workwell-integration folder on local branch integration/local. Repository visibility was restored to public at the owner's request. No integration code was pushed to dev, main or member branches.

## Inputs and scope

The CA6117 project brief requires an observable agent workflow, retrieval grounding, human oversight, a safety response, state and audit logs, plus evaluation evidence. The team allocation selects Python, Streamlit, one model provider per run, local JSON persistence, fictional users and simulated dates. Member A owns the UI and integration into the workflow.

The integration includes all four implementations, not the earlier scaffold. Reports and presentation slides are outside this implementation task.

## Source provenance

| Branch | Source commit | Integrated contribution |
|---|---|---|
| member-a-ui-baseline | a324d1eeb43306e3d8fc0fbbd80bd37d5c42089a | UI, contracts, adapter and A tests |
| member-b-safety-workflow | c641784e9d3ad0cc4d6aef0aa95d441eff5d16fa | Workflow, safety rules, validation and B tests |
| member-c-knowledge-retrieval | 3776918f9dd94bfe13e112b48d98e1593d86e447 | Knowledge base, retrieval, model providers and C tests |
| member-d-memory-feedback | 91cbf74f6b0cf674e24c56f84043045a9887557c | Storage, feedback, demo seeder and D tests |

Files were selected by module ownership into a local A-based checkout. This is a combined working tree, not a remote merge of the member branches. Original branch contributions remain available unchanged in GitHub.

## Integration changes

1. Removed C's translation fields from prompts and output. B requires exactly category, advice, reason and source_ids, so the earlier bilingual actions could not pass its validator. Extra fields and malformed source IDs now produce INVALID_MODEL_OUTPUT.
2. Kept full offline integration separate from A's standalone fixture. Offline plans copy retrieved source content, carry explicit sample labels and pass through real B validation and D storage. The interface and workflow result identify offline_demo, including recovered drafts.
3. Made Team modules the default interface. Added Simulate next day, previous accepted plan identification, and actionable save-error messages. The pending original decision remains available for retry after partial writes.
4. Corrected simulated seed advice that claimed unsupported durations or introduced content cues absent from the seed sources. Seeded history now passes B's validation.
5. Allowed later-date feedback updates to the latest accepted plan when an intervening new plan was rejected. Identical retries remain harmless; conflicting reports for the same or earlier date remain errors. Earlier workflow reports remain in audit inputs.
6. Added provider/model handling for a blank model setting and bounded model requests to 30 seconds with no SDK retries.
7. Updated placeholder interface tests for real C/D behavior. Added complete-pipeline tests and a managed-workspace validation script. Documentation is English; API keys and runtime data are ignored.

## Validation evidence

Environment: Python 3.12.14, Streamlit 1.65.0, pytest 9.1.1. requirements-lock.txt records the clean validation environment. Command: `powershell -NoProfile -ExecutionPolicy Bypass -File .\validate.ps1`.

Latest complete run: **646 passed in 10.03 seconds**, no skipped tests. This includes 27 integration cases, 11 real-response validator regressions, 28 current action-selection cases and the combined member tests. The suite makes no real API requests.

| Case | What actually executed | Result |
|---|---|---|
| First-day draft and human acceptance | Actual A/B/C/D; substituted raw model response | Passed |
| Next-day feedback and new-plan rejection | Actual memory, feedback builder, retrieval, schema checks and JSON writes | Passed |
| Third-day continuation after rejection | Same prior accepted plan; later feedback report | Passed |
| Pending draft after new session | Actual persisted draft reused, no second model call | Passed |
| Duplicate generation/decisions | Actual session handling and idempotent storage/audit writes | Passed |
| Changed form before confirmation | Old draft refused; stored draft remains unaccepted | Passed |
| Six discomfort areas in offline integration | Actual pipeline; no substituted modules and no API call | Passed |
| Seeded history | Actual D seed data through B and C | Passed |
| Warning stop | Actual safety stop before retrieval/model; input logged | Passed |
| No matching sources | Actual retrieval returns empty; model not called | Passed |
| API failure | Substituted external exception; safe error and retry | Passed |
| Malformed JSON/schema/source IDs | Substituted external responses rejected before draft storage | Passed |
| Corrupted JSON data | Actual file preserved; generation blocked | Passed |
| Partial decision audit failure | Actual record save, failed audit substitution, same-decision recovery | Passed |
| Streamlit components | Actual Team modules page: generate, accept, rerun, advance day, feedback, reject and reopened page | Passed |

Additional checks: pip check reported no broken requirements; Python compilation passed. Local Streamlit service started on 127.0.0.1:8517. Both the health endpoint and root page returned HTTP 200. AppTest verifies component behavior; no browser screenshot review is claimed.

## Live verification update

The owner supplied a temporary Zhipu test credential. Exactly three real glm-4-flash requests were made without SDK retries. The key was never written to files or the running preview server. No request was made after the three-call ceiling.

The first response was rejected for an unsupported interval. The second exposed an overly strict generic-break cue check; its recorded response passed after a narrow validator correction and was explicitly accepted in isolated simulated storage. The third received actual prior accepted history and feedback, but introduced every hour. That exposed the numeric-only duration parser. Final validation now recognizes written intervals and rejects that response.

Cached revalidation used the previously received responses and consumed no additional quota. Final next-day live acceptance remains unverified. See live_validation.md and live_validation_evidence.json for a distinction between original outcomes, cached replay and final validation. Eleven offline regression cases protect the corrected validator behavior.

## Bounded selection follow-up

The owner authorized two additional real requests. C now offers only source-linked curated action candidates, and the model selects IDs with personalized reasons. Advice, category and citations are materialized from the catalog. B validates the final plan. The program limits incomplete-feedback plans to the first ranked valid action after validating all returned choices.

The first real call produced a valid three-action plan and its simulated acceptance was saved. The second returned three choices despite the one-action prompt. After correcting count enforcement, that exact recorded real response was replayed with no new request; the resulting one-action plan passed and its simulated rejection was saved. The prior accepted record carries the Partly completed feedback and new fatigue score. No unsupported hourly schedule is present in the advice. This final replay is distinguished from a fresh post-change provider call in live_selection_validation.md and live_selection_evidence.json.

## Current three-day policy

The previous unconditional one-action limit has been removed. The model supplies explicit priority, selection reason, priority reason and adjustment reason for 1-3 actions. C sorts explicit ranks and materializes supported advice. The program groups only approved complementary top-priority break/stretch pairs, preserving all actions and their citations. Daily feedback and score changes are included in adjustment notes, with first-use and observed contradiction guards.

Exactly three real requests advanced through three simulated days with three actions each and decisions accepted, accepted, rejected. Final context-guard changes were checked by replaying those recorded responses without additional requests. See three_day_validation.md and three_day_evidence.json. Earlier sections describe prior investigation stages, not the current truncation policy.

## Practical limits

Source-ID checks and keyword/duration matching do not establish medical correctness or full semantic grounding. Knowledge summaries require source/content review before any real-world use. Current storage supports one local process. Final decisions are irreversible; simulation dates must increase. Form fields are submitted as one snapshot. A refreshed session can recover a pending draft by resubmitting its exact input. Data reset backs up existing records before replacing the demo scenario.

The integrated project is ready for review with the current three-day policy. Real responses and final-code cached replay outcomes are documented separately. Publishing to dev remains a separate action requiring the owner's later instruction.
