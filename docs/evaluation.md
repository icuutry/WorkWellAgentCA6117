# Evaluation and provenance

## Scope

This release organizes the existing integrated implementation for main. It does not change application logic, model prompts or validators. All evaluation uses fictional users. Source was integrated from the four member branches, followed by shared integration fixes.

| Member | Original branch | Integrated source commit |
|---|---|---|
| A | member-a-ui-baseline | a324d1eeb43306e3d8fc0fbbd80bd37d5c42089a |
| B | member-b-safety-workflow | c641784e9d3ad0cc4d6aef0aa95d441eff5d16fa |
| C | member-c-knowledge-retrieval | 3776918f9dd94bfe13e112b48d98e1593d86e447 |
| D | member-d-memory-feedback | 91cbf74f6b0cf674e24c56f84043045a9887557c |

The release preserves the original member commit ancestry using a documented history merge that retains the integrated working tree. Member branches are unchanged. dev at 533b87f is the archived submission source; it includes the detailed historical investigations. Main moves only the recorded selection templates required by simulation into tests/fixtures/provider_selections.json and removes duplicated reports and raw prompt/output bundles.

## Offline verification

The integrated revision passed 666 local tests and GitHub Actions before this release cleanup. After cleanup on 2026-10-14, all 666 local tests passed again in 13.52 seconds; the English/private-file/credential audit passed for all 50 release files. No live API call was made during cleanup. Tests cover input validation, preset warnings, unsupported/unsafe output, source and English checks, ranks/groups, persistence, feedback, corrupt files, immutable decisions, idempotent retries and Streamlit component interactions.

The stress test executes ten independent sequences of five consecutive days: 50 simulated generations, 40 accepted plans, 10 rejected plans, 50 distinct records and 100 distinct audit events. Only the external model boundary is substituted. It makes zero real model requests. Compact results are in five_day_stress_results.json; the complete runnable assertions remain in tests/test_five_day_stress.py.

Hosted offline retesting on 2026-10-13 passed twelve checks: immediate user-history refresh, generation and English sources, saved-decision messages, compact history/audit with closed detail panels, partial completion and next-day generation, user switching, detail expansion, history recovery in a new session, warning stop and mobile layout. Screenshots and full browser captures are separate evaluation attachments, not runtime dependencies.

## Three hosted live generations

On 2026-10-13 the deployed Team modules workflow was exercised exactly three times with a unique fictional user and non-offline results. Each generated three ranked English actions; English sources and approved top-priority grouping were displayed. Decisions were accepted, accepted and rejected, and all were saved. The hosted audit contained three generation and three decision events. Provider-internal request logs were not accessed.

| Simulated date | Sitting hours | Discomfort | Fatigue | Prior completion | Decision |
|---|---|---|---|---|---|
| 2026-10-13 | 6 | 4 | 5 | Not applicable | accepted |
| 2026-10-14 | 6 | 3 | 4 | Partly completed | accepted |
| 2026-10-15 | 6 | 2 | 3 | Completed | rejected |

Workflow completion is not equivalent to factual explanation correctness. The model treated general fatigue as visual fatigue, claimed sitting time decreased despite unchanged six-hour inputs, cited yesterday's score in a current-day priority rationale, and inferred changes in unmeasured physical activity. Current checks did not reject these explanations. Advice is catalog-constrained; generated explanations still require human review. Future work should validate such claims against current/prior facts and use conservative fallbacks without extra model requests.

## Reproduce and deploy

Follow README.md to install runtime/development dependencies and run the offline suite. tests/conftest.py blocks external model requests. Follow streamlit_deployment.md to deploy app.py from main or retain the separate dev demo. Private provider credentials belong only in environment configuration or hosted Secrets. Runtime files, screenshots, temporary helpers and private configuration are excluded from the source release. No durable cloud-history or real-user access-control claim is made.
