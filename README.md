# WorkWell integrated prototype

WorkWell combines the four member branches into a Streamlit classroom prototype for daily check-ins, source retrieval, bounded plan generation, human decisions, persistent memory and next-day feedback. All project content and generated plans use English. Use fictional users and simulated dates.

## Run locally

Python 3.12 is recommended. Create an isolated local `.venv` using the setup commands below; virtual environments are excluded from Git.

Windows PowerShell, from this folder:

```powershell
$env:WORKWELL_OFFLINE="1"
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1
```

Open http://127.0.0.1:8501 and leave `Team modules` selected. Offline integration runs the actual B safety/workflow, C retrieval and D persistence modules. Plans are explicitly marked sample text; no model API is called. `Offline UI preview` is the separate A fixture and does not exercise the complete agent.

For a fresh installation:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

On macOS/Linux, use `python3.12 -m venv .venv` and `.venv/bin/python` in the equivalent commands.

## Normal and next-day demonstrations

1. Start with `demo-user`, simulated date 2026-10-10, sitting time 6, Neck, discomfort 3, fatigue 4, no warnings and completion `Not applicable`.
2. Generate a draft. Review the explicit priorities, selection and adjustment reasons, execution arrangements, English sources, workflow steps and submitted input snapshot. The draft is saved but remains unaccepted.
3. Accept or reject it explicitly. Inspect History and Audit log.
4. Click `Simulate next day`. If an earlier accepted plan exists, report its completion explicitly; the button does not invent completion. Change the scores and generate again.
5. Select a warning such as Numbness to demonstrate the safety stop. No retrieval or model call occurs after that stop.

Do not modify form fields before confirming an existing draft. If fields change, confirmation refuses the stale draft and requires a new check-in. Form fields are submitted together, so an unsubmitted edit does not change the displayed submitted snapshot. Submitting identical input reuses the result. After a browser refresh, submit the exact same pending check-in to recover the persisted draft without another model call. Once a day has a final decision, use a later simulated date.

`Simulate next day` advances the date and clears the displayed result without generating or saving a plan. Do not skip a draft awaiting your decision. After a partial decision save, retry the same decision; the opposite decision is blocked.

## Data and reproducible scenarios

Actual records and audit events are under ignored `runtime_data/`. The A fixture uses ignored `demo_data/`. Use `WORKWELL_DATA_DIR` in the shell to select another actual data directory. JSON files are atomically replaced; corrupt data is reported and preserved. Storage supports one local process, not concurrent processes writing the same directory.

```powershell
.\.venv\Scripts\python.exe demo_seed.py --list
.\.venv\Scripts\python.exe demo_seed.py first_use
.\.venv\Scripts\python.exe demo_seed.py with_history
```

The seeder backs up existing files before resetting. `with_history` supplies an accepted plan on 2026-10-10; submit 2026-10-11 with completion `Partly completed`. Seed records are simulated history, not evidence of a real model call.

## Live model configuration

The latest validation made exactly three real requests and advanced through three simulated days. See `docs/three_day_validation.md` for original outcomes and final-code cached replay. The model returns explicit priorities, selection reasons and daily adjustment reasons for 1-3 supported actions. Partial completion does not force truncation. Approved complementary top-priority actions can share one arrangement while keeping their separate content and citations. Copy `.env.example` to `.env`, choose exactly one provider and supply its key privately. Set `WORKWELL_OFFLINE=0`, restart the app and leave `Team modules` selected. An existing shell variable takes precedence over `.env`; remove or change the shell's offline setting when switching to live mode.

- Zhipu: `WORKWELL_PROVIDER=zhipu`, `WORKWELL_MODEL=glm-4-flash`, `ZHIPU_API_KEY`.
- Anthropic: `WORKWELL_PROVIDER=anthropic`, a supported model, `ANTHROPIC_API_KEY`.
- OpenAI or compatible endpoint: `WORKWELL_PROVIDER=openai`, a supported model, `OPENAI_API_KEY`; optionally `OPENAI_BASE_URL`.

Only the selected provider is called. Each request has a 30-second timeout and no SDK retries. API failure and invalid output stop generation. The workflow never substitutes an offline result after a live failure. Credentials, `.env`, runtime data and `.venv` are excluded from Git. Do not put credentials in screenshots, logs or tracked files.

## Validate

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

This managed workspace restricts the system temporary directory. The included validation script places temporary test files inside the integration folder:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\validate.ps1
```

See `docs/integration_report.md` for provenance and `docs/three_day_validation.md` for the latest policy, tests and real-response evidence. The report distinguishes real module execution from a substituted external model response. `docs/real_call_evidence.md` describes earlier member-C evidence, not a validated run of this revision.

## Module responsibilities

| Module | Responsibility |
|---|---|
| app.py | A interface, session state, adapter, decisions, history and audit display |
| workflow.py and safety.py | B deterministic ordering, stop conditions and validation |
| retrieval.py and llm.py | C retrieval, source-linked action selection, reasons and model calls |
| storage.py, feedback.py and demo_seed.py | D atomic persistence, memory, feedback and simulated scenarios |
| contracts.py and INTERFACES.md | Shared result envelope and schemas |

The content checks are conservative heuristics. Legal source IDs and matching words do not establish clinical correctness or full semantic support. This is a course prototype, not a clinical system.

## Documentation and deployment

- `docs/module_guide.md`: purposes, ownership, interfaces, daily lifecycle and runtime modes.
- `docs/streamlit_deployment.md`: exact dev/app.py deployment steps, offline configuration, private Secrets, verification and troubleshooting.
- `docs/final_review.md`: final English/credential audit and five-day simulation results.
- `docs/three_day_validation.md`: historical real-provider investigation and replay disclosure.

Deployment target: `icuutry/WorkWellAgentCA6117`, branch `dev`, entry point `app.py`, Python 3.12. Keep `main` as the GitHub default if desired. Start the hosted demo with `WORKWELL_OFFLINE = "1"` in Streamlit Secrets; no private key is included in the repository. GitHub push and hosted deployment are separate operations.
