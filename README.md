# WorkWell Demo

A classroom prototype for work-break planning and fatigue management, developed by a four-person team. Member A's Streamlit interface and standalone offline UI fixture are available. The actual B/C/D modules are placeholders that explicitly return NOT_IMPLEMENTED. The fixture does not call a language model, and its source placeholders are not health evidence.

Use fictional users and simulated data only. This version is a single-machine classroom prototype, unsuitable for actual employee health management.

## Uploading to an existing GitHub repository

Download and extract the ZIP, then copy the code and documents inside this directory to the root of your existing repository. The root should directly contain app.py, INTERFACES.md, requirements.txt, and the other files. Do not add an extra enclosing folder or upload only the ZIP: GitHub does not automatically extract it into source files.

Upload to your own `a/ui-baseline` branch and open a PR. Merge into main after all four members confirm INTERFACES.md. This initial scaffold includes B/C/D placeholders. If teammates already have implementations with the same filenames, compare them first rather than overwriting them. Include dotfiles such as .github, .gitignore, .env.example, and .python-version when copying.

## Files and ownership

```text
app.py                         A: UI, buttons, team adapter, offline UI fixture
contracts.py                   Team: enums and shared result format
workflow.py / safety.py         B: workflow and safety rules; placeholders
retrieval.py / llm.py           C: retrieval and model calls; placeholders
storage.py / feedback.py        D: storage and feedback; placeholders
data/knowledge.json            C: knowledge base; currently empty
tests/                         Logic, interface and Streamlit component tests
INTERFACES.md                   Shared interface contract
CONTRIBUTING.md                 Branch, PR, dependency and testing rules
requirements.txt               UI runtime dependencies
requirements-dev.txt           Runtime and test dependencies
.github/workflows/tests.yml     GitHub automated tests
.github/pull_request_template.md
.env.example                   Empty configuration template; no actual secrets
.gitignore / .python-version / pyproject.toml
```

demo_data and runtime_data are runtime directories and must not be uploaded. The offline fixture currently uses demo_data. Member D's actual storage should use runtime_data.

## Python and virtual environments

The team uses Python 3.12.x. Each member creates their own `.venv` on their computer and installs from the same dependency files. `.python-version` records the agreed version; it does not install Python or ensure that your system python command uses that version.

Windows PowerShell, from the repository root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Calling the virtual environment's interpreter directly avoids changing the PowerShell execution policy. If `py` is unavailable, first verify that `python --version` is 3.12.x, then use `python -m venv .venv`.

macOS / Linux:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest
.venv/bin/python -m streamlit run app.py
```

Install requirements.txt if you only need to run the page. For development, use requirements-dev.txt, which includes runtime dependencies. Do not commit .venv. Team members do not need identical directory paths.

## Using the page

The default mode is Offline UI preview. Fill out the form, generate a sample, accept or reject it, and view history and logs. Use increasing simulated dates for subsequent feedback. Warning input triggers a sample stop.

Accepting or rejecting does not call the generation function again. If you change any form field before confirmation, the old draft is invalidated and a new plan is required. Submitting identical input keeps the current successful result; an error result can be retried. A browser refresh may recreate the session and clear unsaved drafts, while saved records remain available.

Select Team modules for actual integration. Its interfaces use the shared envelope in INTERFACES.md. B/D should not reuse the list-return interfaces from the earlier member-A README. Unimplemented modules report explicit errors and never silently fall back to fixtures.

## Integrating the actual modules

1. All four members confirm INTERFACES.md; it and contracts.py define the shared contract.
2. B implements workflow and checks, C implements retrieval and model calls, and D implements storage and feedback.
3. After choosing one model provider, C adds its SDK dependency and private configuration loading through a PR. .env.example is currently only a template; the program does not automatically load .env.
4. A's TeamBackend is already connected to workflow.start_workflow, workflow.submit_decision, storage.load_history, and storage.load_logs.
5. Each member adds tests for their module. After integration, run normal-input, next-day-feedback, and safety-stop scenarios.

Never put API keys in source code or commit them. `.gitignore` only ignores untracked files; it cannot automatically remove keys or data already uploaded.

## Shared test command

Run `python -m pytest` using the project's virtual environment. The Windows/macOS commands above use the full interpreter path to run the same tests.

- tests/test_app.py: repeated operations, stale-plan prevention, history and feedback, sample stops, corrupted-file protection, and save retries.
- tests/test_interfaces.py: shared result format, adapter boundaries, and explicit error behavior of the current placeholders.
- tests/test_ui.py: Streamlit AppTest checks for button states, confirmation, and changed fields.

CI uses Python 3.12 and runs the same command. Uploading CI files does not enable main branch protection; see CONTRIBUTING.md for setup instructions.

LangChain, vector databases, Docker, and complex deployment are unnecessary for the current demo. Complete the modules first, then consider extensions.

## Suggested Git workflow

The GitHub website or GitHub Desktop can also be used. If you have already cloned the repository, prepare your branch as follows:

```bash
git switch main
git pull
git switch -c a/ui-baseline
```

After copying the package files, review the changes and .gitignore before committing and pushing:

```bash
git status
git diff
git add .
git commit -m "feat(ui): add WorkWell page and shared repository scaffold"
git push -u origin a/ui-baseline
```

Then open a PR on GitHub. If a branch or implementation with the same name already exists, discuss it first. Do not use force push to overwrite teammates' work.
