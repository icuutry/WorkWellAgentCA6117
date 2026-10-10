# WorkWell demo safety rules

These rules define Member B's programmed stop conditions for the classroom demo. They use the four warning options already declared in `contracts.WARNING_SIGNS` and preserve the existing interface. They apply to fictional users and simulated data. They are project safeguards, not clinical diagnostic criteria or a validated medical triage system.

## Preset stop conditions

| Rule | Exact input option | Meaning | Program response |
|---|---|---|---|
| B-S01 | `Numbness` | User reports numbness | Stop routine work-break advice |
| B-S02 | `Radiating pain` | User reports pain spreading to another area | Stop routine work-break advice |
| B-S03 | `Severe headache` | User reports a severe headache | Stop routine work-break advice |
| B-S04 | `Persistent worsening discomfort` | User reports discomfort that keeps getting worse | Stop routine work-break advice |

Any one selected option triggers `status="stopped"`, `error_code="SAFETY_STOP"`, and an empty `data` dictionary. The display message lists the selected warning options, explains that routine work-break advice has stopped, and asks the user to seek professional medical advice. Multiple selections still produce one stop result, with all selected options explained.

The list is defined by the team's existing input contract. The choice to stop for every selection is a conservative engineering decision for this demo; it is not a claim that these four broad labels share one clinical urgency level.

## Function behavior

`check_safety(check_in: dict, history: list[dict]) -> dict` first calls `validate_input`. Invalid input returns `error/INVALID_INPUT`; the program must stop before generating a plan.

For valid input, selected warning signs take priority over unavailable or malformed history. The current warning can be detected without a working storage module. If no warning is selected, history must be a JSON-serializable list of dictionaries with finite numeric values; malformed history returns `error/STORAGE_ERROR`.

When valid input contains no selected warning and the supplied history has the expected outer format, the function returns `ok`, an empty `data` dictionary, and the message "No preset warning signs selected." This result means only that the implemented preset check found no selection. It does not establish that a person is medically safe.

The returned `trace` records the input-validation step and, when reached, the safety-check step. Full record validation, user/date consistency, feedback linkage, history interpretation, and persistent audit logging are the workflow and storage modules' responsibilities.

## Workflow integration

Member B's workflow must run the programmed safety gate before retrieval or model generation. Every result other than `ok` stops the normal route. A warning stop must be logged with its input, reason, time, and actual steps. A log write failure must be reported without resuming normal plan generation.

This function performs no model call and no disk write. The current step implements the safety gate; the workflow and its persistent audit logging will be implemented separately.

## Input is data

Strings such as "ignore safety rules" in a user identifier, additional input fields, or history notes have no authority to change these rules. A field such as `disable_safety=true` is not a recognized override. Unknown warning labels and duplicate selections are rejected by input validation. C must use actual retrieved sources for any later plan, and the model cannot override B's programmed stop.

## Basis and limits

The following public sources explain the background for conservative stopping. They concern particular symptoms and clinical contexts, and do not validate this demo's four-label algorithm.

- [North Bristol NHS Trust neck injuries](https://www.nbt.nhs.uk/our-services/a-z-services/emergency-zone/ed-miu-patient-information/neck-injuries) advises stopping the leaflet's exercises and contacting a doctor when certain symptoms consistently occur, including numbness and pain spreading into an arm. This provides background for B-S01 and B-S02; the leaflet concerns neck injuries rather than all office discomfort.
- [NHS headaches](https://www.nhs.uk/symptoms/headaches/) distinguishes situations needing different levels of help, including sudden extremely painful headaches and headaches with other concerning symptoms. B-S03 is a broader project stop label, not a substitute for that assessment.
- [NHS back pain](https://www.nhs.uk/conditions/back-pain/) advises seeking help for some persistent or rapidly worsening pain and stopping the listed exercises if pain worsens. This provides background for B-S04; the demo's label does not specify clinical duration, onset, or urgency.

References were checked on 2026-10-10. The demo does not capture every warning sign, infer symptoms from free text, diagnose disease, prescribe treatment, or assess urgency. It applies the selected current warning options only; it does not derive a new warning selection or a medical trend from historical scores. A high or low self-reported score alone is not a new clinical threshold in this version. Broader rules would require a documented contract update and further review.

## Shared demonstration cases

Use a valid check-in with all required fields and `previous_completion="Not applicable"` when history is empty. For a normal case, use `warning_signs=[]`. For a warning case, use `warning_signs=["Numbness"]`; each of the other three options must independently stop as well. For an override-attempt case, keep a valid warning selection and add a note asking to ignore the rules; the result must remain `stopped/SAFETY_STOP`.

`tests/test_safety_stop.py` covers these cases, multiple warnings, invalid input, malformed history, preserved input snapshots, and attempted overrides. Run the shared test command using the project's virtual environment.
