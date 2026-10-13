# Three day daily workflow validation

Date: 2026-10-13. This round made exactly **three real Zhipu glm-4-flash requests**, one for each simulated day. SDK retries were disabled, timeout was 30 seconds and each output was capped at 1024 tokens. No additional real requests were made.

## Current behavior

The model selects one to three source-linked actions and returns action_id, priority, reason, priority_reason and adjustment_reason. Priorities must be distinct consecutive integers from one. The program sorts by these explicit values, never by implicit response order. Partial completion does not automatically discard actions or force a one-action plan.

Advice, category and citations come from the curated action catalog. All source titles, content and source names are maintained in English. Script checks reject non-Latin source content, while the curated knowledge entries have been reviewed as English; script checks alone are not a complete language classifier.

The program can group priorities one and two only for the explicitly approved complementary pairs: a short walk plus gentle neck/shoulder stretches, or a standing/position-change break plus those stretches. Other pairs stay separate. Groups retain every underlying action and its separate citations. B rejects groups that omit, duplicate or arbitrarily combine actions. Final plans have one to three actions even when the number of execution arrangements is smaller.

The interface displays explicit priority, selection rationale, priority rationale, daily adjustment and execution arrangements. Feedback remains daily; no hourly feedback scheduler is added. Accept/reject decisions, next-day completion and scores are persisted and audited.

## Three-day evidence

| Simulated day | Feedback | Discomfort / fatigue | Actions | Human decision |
|---|---|---|---:|---|
| 2026-10-13 | First use, Not applicable | 3 / 4 | 3 | Accepted |
| 2026-10-14 | Previous plan Partly completed | 3 / 6 | 3 | Accepted |
| 2026-10-15 | Previous plan Completed | 2 / 3 | 3 | Rejected |

All three responses yielded valid source-linked choices with explicit priorities. The selected set and ranks remained the same: neck/shoulder stretches, standing/position change, then short walking. The first two form one approved execution arrangement; walking remains a separate action. This sample does not demonstrate that the model found an optimal priority ordering or that priorities must change whenever scores change.

Day two's feedback was linked to day one's accepted record. Day three's feedback was linked to day two's accepted record. Rejecting day three did not erase history or turn it into an accepted plan. Final isolated history has decisions accepted, accepted, rejected and complete audit events.

## Context corrections and replay disclosure

The first response wrongly used unchanged-score language without earlier history. First-use adjustment text is now supplied from the actual absence of accepted history.

Later responses included a no-significant-change fatigue phrase despite changing scores, and statements attributing improvement to an action. Adjustment notes now include actual persisted completion and prior/current scores. Recognized contradictions and the observed causal phrases are replaced with a conservative explanation that self-reported changes do not establish what caused them. These text guards cover observed cases, not all possible semantic errors; generated reasons still need human review.

After those guards were finalized, all three recorded real responses were replayed through the complete final workflow and storage in a separate isolated directory. The replay made **zero external API requests**. It is final-code validation using real recorded responses, not three fresh provider requests after the last guard changes. Original responses and final replay outcomes are preserved in three_day_evidence.json.

## Local verification and release

Latest complete local run: **646 passed in 10.03 seconds**. Tests include explicit priorities independent of list order, retention of multiple actions under incomplete feedback, exact catalog advice, merge compatibility, preservation of sources, rejection of manipulated groups, English source checks, clinical scope checks, and daily-context corrections. The regression suite makes no real API calls.

The supplied credential existed only in temporary process environment variables. No private .env or Streamlit secrets file was created. Runtime test data, virtual environments, Git metadata and test helper files are excluded from the release archive. Empty configuration templates contain key names only. No code has been pushed to dev, main or member branches.

This remains a proof of concept using fictional data. Format, references and conservative scope checks do not establish medical correctness, comprehensive semantic grounding or clinical efficacy.
