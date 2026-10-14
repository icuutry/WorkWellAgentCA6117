# WorkWell collaboration guidelines

## Ownership and branches

A owns the interface, B safety/workflow, C retrieval/model calls and D storage/feedback. contracts.py, INTERFACES.md, dependency files and integration documentation are shared. Review changes with the affected member before publishing them.

Use dev for integration and main for reviewed releases. Original member branches remain available. The main release preserves their commit ancestry through an explicit history merge while retaining the already integrated working tree. Use pull requests for subsequent shared changes; avoid force pushes and overwriting member branches.

## Development

Use Python 3.12 and a private local virtual environment. Keep runtime dependencies in requirements.txt and test dependencies in requirements-dev.txt. The optional validated environment snapshot is requirements-lock.txt. Never commit .venv, .env, API keys, runtime records or temporary test directories.

All integrated source files, interface text, documentation and generated plans use English. Change INTERFACES.md alongside any schema changes. Do not silently fall back to sample plans when a live operation fails.

## Validation

Run `python -m pytest -q` in the virtual environment, or validate.ps1 in the managed Windows workspace. Tests use isolated data directories and substituted model responses, so they need no credentials. Check generation, acceptance/rejection, stale inputs, next-day feedback, safe stops, history, audit display and recovery after failures.

Streamlit AppTest exercises actual components. It does not establish browser visual quality or verify a real model provider. Record live API evidence separately after credentials are supplied.

The repository owner has requested public visibility. Publishing code still requires keeping private configuration and runtime data out of commits. Repository visibility and code publishing are separate actions.
