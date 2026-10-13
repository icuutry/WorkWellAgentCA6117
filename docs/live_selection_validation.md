# Bounded action selection validation

Historical test report. The current priority and daily-feedback policy is documented in three_day_validation.md; earlier one-action restrictions are superseded.
Date: 2026-10-13. This follow-up was authorized for exactly two real API calls. Both used Zhipu glm-4-flash with SDK retries disabled, a 30-second timeout and a 1024-token output cap. No third request was made in this round. Together with the earlier investigation, five real requests have been made across the two rounds.

## Implementation

The model no longer writes the advice body. data/action_catalog.json supplies thirteen English action candidates linked to the existing knowledge entries. Only candidates whose sources were retrieved for the current check-in are offered to the model.

The provider returns selections containing action_id and reason. The program validates IDs, duplicates, exact fields and English reasons, then fills immutable advice, category and source_ids from the catalog. Unknown actions, extra advice fields and unsupported source selections are errors. B still validates the final plan and a human must explicitly accept or reject it.

For Partly completed or Not completed feedback, the program retains the model's highest-ranked valid selection as a single action. Every returned selection is validated before applying that limit, so an invalid lower-ranked selection cannot be hidden by truncation. Other completion states permit up to three actions. Plan size is controlled by the program rather than reliance on prompt compliance.

The catalog is a bounded action vocabulary, not a substitute API response: the real model chooses actions and supplies reasons using actual input, retrieved guidance and stored feedback. Advice is intentionally constrained rather than freely rewritten. Reasons remain generated text and require human review; clinical correctness is not established by these tests.

## Two-call results

| Case | Real requests | Original outcome | Final outcome |
|---|---:|---|---|
| First day, no history | 1 | Three valid source-linked selections | Draft passed B validation; explicit simulated acceptance and audit saved |
| Next day, Partly completed, fatigue 4 to 6 | 1 | Three valid selections despite the one-action prompt | Recorded response passed after deterministic size enforcement; one-action draft and explicit simulated rejection saved |

The next-day response used the previous accepted plan and mentioned partly completed work and changed fatigue. The first plan contained three actions; the final next-day plan contained one supported neck/shoulder stretching action. No invented hourly interval is present in its advice.

The initial next-day parser rejected the three returned selections. The count policy was corrected locally after the second request. Final revalidation replayed that exact recorded real response through the actual workflow, storage and UI decision handler, using **zero additional API requests**. This is cached-response validation, not a fresh live response generated after the last code change.

The final isolated history contains an accepted first-day record and a rejected next-day record. Partly completed feedback and the new scores are linked to the first accepted plan. Record and audit writes completed successfully. live_selection_evidence.json preserves the initial rejection and final replay outcome.

## Regression and privacy checks

Latest complete offline run: **629 passed in 5.32 seconds**. Eleven new action-selection tests cover all catalog entries against B's validator, exact advice materialization, unknown or unretrieved IDs, duplicates, override attempts and deterministic reduction under incomplete feedback. Tests make no external requests.

The credential existed only in the test process environment. No .env was created and no credential was written to source, reports, logs or Git commits. Test data is under ignored artifacts/live-selection-validation. The existing preview server remains offline. No integration code has been pushed to dev or main.
