# Live API validation

Historical test report. The current priority and daily-feedback policy is documented in three_day_validation.md; earlier one-action restrictions are superseded.
Date: 2026-10-13. Provider: Zhipu. Model: glm-4-flash. Exactly **three real API requests** were made. SDK retries were disabled, request timeout was 30 seconds and output was capped at 1024 tokens. No further requests were made after the three-request ceiling.

The supplied test credential existed only in temporary process environment variables. It was never written to a project file, .env, report, audit record or Git commit. The existing preview server remains in offline mode and has no supplied credential. No code has been pushed to dev or main.

## Outcomes

| Sequence | Real requests | Case | Outcome |
|---|---:|---|---|
| 1 | 1 | First-day generation | Rejected: invented numeric interval absent from cited guidance |
| 2 | 1 | First day with qualitative-advice prompt | Initially rejected: generic break label alongside supported stretching |
| Replay of 2 | 0 | Same input and recorded real response after validator correction | Valid draft; explicit simulated acceptance and audit saved |
| 3 | 1 | Next day, previous plan partly completed, fatigue increased | Real response received historical context; added unsupported every hour interval |
| Replay of 3 | 0 | Final validator against the recorded response and valid accepted history | Rejected: unsupported written interval; no new draft or decision saved |

The third response initially passed the earlier parser because it only recognized numeric durations. That was a validation gap. The final parser detects every hour and common number-word durations. Final acceptance of the third response is **not** claimed.

The isolated final revalidation store contains one valid accepted first-day plan. Next-day feedback is linked to that plan; the rejected model output is recorded as a workflow error. Cached revalidation is explicitly identified as replay of a previous real response and consumes no API quota. It is not a new live call.

## Fixes and regression coverage

- The model receives each retrieved source's category and is told to use supported qualitative action wording without adding schedules.
- Incomplete previous completion requests one smaller action. The next-day request contained the prior accepted plan, its actions, Partly completed and the changed fatigue score.
- A generic break label may accompany a specific supported action for sources curated as break guidance. Unsupported specific actions and break-only unsupported instructions remain rejected.
- Common written durations and implicit intervals are checked against source content. Invented schedules are rejected whether written as digits or words.
- All output remains English and uses the exact action schema. There is no automatic API retry or silent replacement of rejected advice.

Latest full offline regression run: **618 passed in 5.36 seconds**. Eleven cases in tests/test_live_regressions.py cover the observed validator failures and ensure unsupported actions, schedules and clinical text remain rejected. Running the suite makes no real API requests.

Sanitized machine-readable evidence is in live_validation_evidence.json. It preserves original outcomes and the final revalidation outcome so an earlier false acceptance cannot be mistaken for final success. Runtime test files remain under ignored artifacts/live-validation.

## Status of this earlier round

Successful final next-day live generation is still unverified: the recorded response was rejected. The three-request allowance for this test run has been exhausted, so no additional request was attempted. Any future live test should be explicitly budgeted and use private process configuration. The final submission must contain no supplied credential.

## Follow-up

The owner later authorized two additional requests. See live_selection_validation.md for the bounded selection implementation and the final next-day cached revalidation outcome. This document retains the original three-request investigation history.
