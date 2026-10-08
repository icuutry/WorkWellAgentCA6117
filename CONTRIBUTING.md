# Four-person collaboration guidelines

## Task ownership

- A: app.py, tests/test_app.py, and tests/test_ui.py.
- B: workflow.py, safety.py, and additional tests for those modules.
- C: retrieval.py, llm.py, data/knowledge.json, and additional tests for those modules.
- D: storage.py, feedback.py, and additional tests for those modules.
- Shared files: INTERFACES.md, contracts.py, requirements files, README, and CI. Ask at least one affected member to review changes to these files.

Do not directly replace a teammate's completed module with a file of the same name. B/C/D files in this package are scaffolds. Compare existing implementations with the contract before merging.

## Branches and pull requests

main contains the shared runnable version. Initially upload A's interface and the base scaffold to `a/ui-baseline`, then merge into main through a PR after confirming the interfaces. Create subsequent branches for small features, such as a/form-validation, b/safety-stop, c/knowledge-retrieval, and d/history-storage. Avoid having all four members edit one shared branch simultaneously.

Each PR should address one small feature that can be explained and verified. Open a PR when the feature is complete and tests pass. A daily progress discussion is sufficient; no fixed number of merges is required. Use Draft PRs to discuss unfinished work, without describing incomplete functionality as available.

Example commit messages: `feat(ui): add confirmation buttons`, `fix(storage): avoid duplicate records`, `docs: clarify plan format`, and `test: cover warning input`. Commit descriptions may also be written in Chinese; the important point is to describe the concrete change.

At least one other member should review each PR for contract compatibility, passing tests, and exposed secrets or runtime data. After merging, teammates synchronize with the latest main before starting their next task. Do not resolve conflicts by overwriting teammates' work.

## Branch protection

The repository administrator configures branch protection or a ruleset for main in GitHub Settings:

1. Require pull requests before merging.
2. Require at least one approval.
3. After CI runs successfully once, require the `Python 3.12 tests` status check.
4. Disable force pushes and deletion of main.

Uploading files does not enable these settings. Availability depends on repository visibility and the GitHub account plan. If protection is unavailable for your current private free repository, follow the PR process manually rather than immediately paying for this demo. Do not make the repository public without the entire team's agreement.

## Environments and dependencies

Use Python 3.12.x throughout the team. Prefer the same patch version, but different 3.12 patch versions do not automatically require rebuilding environments. Each member creates their own local `.venv`; do not share or upload virtual environment directories. Identical computer paths are unnecessary.

Runtime dependencies belong in requirements.txt; test dependencies belong in requirements-dev.txt. When adding a model SDK, C updates the shared dependencies and configuration instructions through a PR. The direct Streamlit dependency is pinned, while pytest allows a compatible range. This is not a complete transitive dependency lockfile.

For stricter reproducibility, create and validate a lockfile in a dedicated clean environment after the first integration is stable. Do not overwrite the shared files with every package from your personal `pip freeze`; that can introduce unrelated packages and machine-specific dependencies.

## Testing

The shared command is `python -m pytest`. Each member adds tests for the important behavior they actually implement, prioritizing errors, stop conditions, and record consistency. Model tests use simulated responses by default; they need no actual API key or paid calls.

CI runs on PRs and commits to main. Passing tests do not mean the unimplemented B/C/D modules are complete. When implementing a placeholder, replace the tests in tests/test_interfaces.py that specifically expect NOT_IMPLEMENTED with tests of the actual module behavior, while retaining contract and adapter tests.

Changes to app.py require checks in the actual page: generation, acceptance/rejection, input changes, safety stops, history, and logs. AppTest checks component interactions but does not fully replace manual browser checks of the display.

## References

- [GitHub branch protection](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)
- [Python venv](https://docs.python.org/3.12/library/venv.html)
- [pytest getting started](https://docs.pytest.org/en/stable/getting-started.html)
