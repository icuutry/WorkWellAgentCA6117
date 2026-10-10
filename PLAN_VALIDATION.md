# WorkWell plan validation

Member B's `validate_plan(plan: dict, sources: list[dict]) -> dict` checks a generated draft before the workflow saves it or sends it to A for human confirmation. It uses the existing plan fields and action categories. The UI remains in English, and the content checks in this version are designed for English office-break advice.

## Structure and references

- A plan contains exactly `plan_id` and `actions`. The plan ID is a non-empty string. The workflow must generate that ID on the server before calling this function; string validation alone cannot establish its origin or uniqueness.
- `actions` contains one to three dictionaries. Each contains exactly `category`, `advice`, `reason`, and `source_ids`. Unknown model fields are rejected rather than treated as overrides.
- The category is `break`, `workstation`, `screen_rest`, or `fatigue_management`. Advice and reason are non-empty strings.
- Each action cites a non-empty list of source IDs from the sources retrieved for the current result. Source IDs must resolve unambiguously: duplicate IDs in the retrieved source list are rejected. Repeating the same valid ID within an action is allowed by the existing contract.
- Each source has non-empty string fields `id`, `title`, `content`, and `url`. Other JSON-serializable source metadata, such as tags, may be present.
- Source URLs must parse as HTTP or HTTPS addresses with a host, no embedded username/password, no whitespace, and a valid port if specified. URLs are not opened by this function. C is responsible for selecting actual original sources and checking their authenticity.
- All plan and source values must be JSON-serializable and finite. The returned plan is an independent snapshot; validation does not modify its input.

## Basic content scope

An allowed category does not make arbitrary advice acceptable. A deterministic filter rejects selected English diagnosis, treatment, prescription, medication, and safety-override expressions in advice and reason. The filter includes some medication names and diagnostic assertions. It can produce false positives, including negated clinical wording, and does not identify every possible clinical statement.

The category-specific content cues below must appear in the advice. Every recognized advice cue must also appear, or have one of the implemented close word forms, in the content of the action's cited sources. Uncited retrieved content cannot satisfy this check.

| Category | Recognized cue groups |
|---|---|
| `break` | break or pause or rest; stand; walk; move; stretch |
| `workstation` | desk; chair or seat; monitor or screen or display; keyboard; mouse; wrist; posture or alignment; height or level; position |
| `screen_rest` | screen or monitor or display; eye or vision; look or gaze; distance or distant or far or away; blink; rest or break or pause |
| `fatigue_management` | rest or break or pause; sleep; water or hydration; relax; breathing; stress; pace; fatigue or tiredness |

For example, a standing-break action is rejected if its only cited source discusses chair height and monitor position. Advice with no recognized cue is rejected. C should choose ordinary office actions that are directly supported by the retrieved material.

Explicit numeric time durations in advice must be positive and also occur in its cited content. Seconds, minutes, and hours are compared in equivalent units, so one minute matches sixty seconds. This check does not infer duration from number words, evaluate every quantity, or distinguish every possible timing context. It does not check numbers in reasons because reasons may describe the current check-in or history; the workflow passes that context to C.

## Return and workflow handling

Success returns `ok`, `data={"plan": validated_snapshot}`, and a `validate_plan` trace step. Failure returns `error/INVALID_MODEL_OUTPUT`, an empty data dictionary, a user-safe explanation, and an error trace step. No raw model payload or stack trace is copied into an error message.

The workflow should detect an empty retrieval result before model generation and return `NO_SOURCES`. Passing empty sources directly to this validator produces `INVALID_MODEL_OUTPUT`. It must stop on any validation failure, retain no accepted plan, and log the actual failure. Only a valid draft can enter `awaiting_confirmation`; this function does not accept a plan on the user's behalf or write a record.

## Limits and testing

These are schema checks and conservative text filters. They are not a medical accuracy assessment, a full semantic entailment check, or proof that a source is authoritative. Matching words, time values, and valid IDs cannot prove that an action follows the source correctly. Negation, context, paraphrases, other languages, and clinical nuance are incompletely handled. C must ensure that the generated advice actually follows the retrieved guidance, and human reviewers must inspect advice with its sources during integration. The demo uses fictional users and simulated data.

`tests/test_plan_validation.py` covers allowed and invalid action counts, categories, missing fields, citations, source metadata and URLs, explicit out-of-scope text, mismatched content, invented durations, and preserved snapshots. Its guidance and example.org URLs are synthetic test fixtures and are not health evidence. Existing input and safety-stop tests remain part of the shared suite.
