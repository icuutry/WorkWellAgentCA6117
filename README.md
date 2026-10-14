# WorkWell

WorkWell is an English Streamlit proof of concept for daily desk-work check-ins. It combines source retrieval, bounded model selections, safety checks, human acceptance or rejection, stored history and next-day feedback. Use fictional users and simulated dates.

## Install and run

Python 3.12 is supported; the validated local version is 3.12.14. From the repository root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:WORKWELL_OFFLINE="1"
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Open http://localhost:8501 and select Team modules. On macOS/Linux use python3.12 and .venv/bin/python; set WORKWELL_OFFLINE=1 with your shell's environment syntax. Codespaces uses Python 3.12, installs development dependencies and defaults to offline mode; start the same Streamlit command from its terminal.

## Demonstrate the workflow

1. Enter a unique fictional user ID. Press Enter or leave the field to refresh history without generating a plan.
2. Use today's simulated date, sitting time 6, Neck, discomfort 3, fatigue 4, no warnings and completion Not applicable.
3. Generate a plan. Review priorities, selection reasons, adjustment reasons, execution groups, retrieved English sources and workflow steps.
4. Explicitly accept or reject the unchanged draft. History and Audit log show compact summaries and expandable complete JSON.
5. Simulate next day. Report completion of the previous accepted plan, update scores and generate again.
6. Use a separate fictional user with Numbness selected to demonstrate a safe stop before retrieval or model use.

Changing a submitted input prevents confirmation of its old draft. Changing users clears the displayed result. If a decision save fails, retry the original decision; user switching is disabled while it is pending. Use increasing dates. Exact pending input can recover a stored draft after refresh without generating again. Viewing history, accepting/rejecting and advancing dates do not call the model.

## Runtime modes and provider configuration

- Team modules with WORKWELL_OFFLINE=1 runs real workflow, retrieval, validation and storage using labelled sample advice. No model is called.
- Team modules with WORKWELL_OFFLINE=0 calls the selected provider for a new valid check-in. Live failures do not fall back to samples.
- Offline UI preview is the separate interface fixture, not the complete workflow.

For live operation, copy .env.example to a private .env or configure hosted Secrets. Set WORKWELL_OFFLINE=0, WORKWELL_PROVIDER=zhipu, WORKWELL_MODEL=glm-4-flash and a private ZHIPU_API_KEY. Anthropic and OpenAI are also supported with their corresponding environment keys. Restart after configuration changes. Existing environment values take precedence over .env. Each request has a 30-second timeout and no SDK retries. Never commit keys or private configuration.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe tools\audit_release.py
```

On the managed Windows workspace, use .\validate.ps1 to put temporary test files inside the workspace. Tests block external requests and use isolated storage; no API key is required. GitHub Actions runs audit and tests on dev/main pushes and relevant pull requests. requirements.txt defines runtime versions/ranges, requirements-dev.txt adds pytest, and requirements-lock.txt records the tested environment.

## Source and documentation

| File or directory | Purpose |
|---|---|
| app.py | A: English interface, user switching, submitted snapshots, decisions and summaries |
| workflow.py, safety.py | B: orchestration, safe stops, output checks and retry handling |
| retrieval.py, llm.py, data/ | C: curated knowledge, retrieval, bounded model selection and explanations |
| storage.py, feedback.py, demo_seed.py | D: JSON persistence, feedback and reproducible fictional scenarios |
| contracts.py, INTERFACES.md | Shared schemas, priorities and approved execution groups |
| tests/, tests/fixtures/ | Unit, integration, UI and offline simulation tests with minimal fixtures |
| docs/module_guide.md | Detailed responsibilities, configuration, lifecycle and limits |
| docs/streamlit_deployment.md | Hosting, private provider setup and evaluation steps |
| docs/evaluation.md | Test results, source provenance and known errors |
| SAFETY_RULES.md | Warning-stop rules and demonstration cases |

## Hosting and storage

Current dev demonstration: https://workwellagentca6117-nxjw3hxhk7qdph9knoxhs6.streamlit.app/

For a main deployment select repository icuutry/WorkWellAgentCA6117, branch main, entry app.py and Python 3.12. Deployment instructions cover both offline and live Secrets. main updates do not change the existing dev deployment.

Actual records and audit events use ignored runtime_data/; WORKWELL_DATA_DIR can select another directory. The UI fixture uses ignored demo_data/. demo_seed.py --list lists reproducible scenarios and backs up files before a reset. Local cloud disk is not durable storage across rebuilds or restarts. The prototype supports one process and has no real-user authentication; fictional IDs filter histories but are not access controls.

## Known limits

This is general desk-work guidance, not diagnosis or treatment. Source IDs, bounded advice and heuristic content checks do not prove clinical correctness or complete semantic grounding. Live tests found incorrect score references and unsupported claims in model-generated explanations that current checks did not reject. These remain documented limitations; the release cleanup does not claim to fix them. See docs/evaluation.md.

main keeps maintainable source, runnable tests and current documentation. Detailed historical reports remain in dev and the separate dev submission archive. Member histories are preserved in main without replacing the integrated files with old branch versions.
