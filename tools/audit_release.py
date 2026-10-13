"""Audit tracked and publishable files without printing any credential value."""
import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PRIVATE_PARTS = {".git", ".venv", ".local-tmp", ".test-tmp", ".pytest_cache", "__pycache__",
                 "runtime_data", "demo_data", "artifacts"}
TOKEN = re.compile(r"\b[a-fA-F0-9]{24,40}\.[A-Za-z0-9_-]{16,64}\b|\bgh[pousr]_[A-Za-z0-9]{30,}\b|\bsk-[A-Za-z0-9_-]{32,}\b")


def audit():
    names = subprocess.check_output(["git", "ls-files", "--cached", "--others", "--exclude-standard"],
                                    cwd=ROOT, text=True).splitlines()
    failures = []
    count = 0
    for name in sorted(set(names)):
        path = ROOT / name
        if not path.is_file():
            continue
        count += 1
        if (any(part in PRIVATE_PARTS for part in path.relative_to(ROOT).parts)
                or path.name == ".env" or path.name.startswith("secrets.")):
            failures.append({"file": name, "issue": "Private file must not be published"})
            continue
        try:
            content = path.read_text(encoding="utf-8-sig")
        except UnicodeError:
            failures.append({"file": name, "issue": "Unexpected non-text release file"})
            continue
        if TOKEN.search(content):
            failures.append({"file": name, "issue": "Credential pattern found; value suppressed"})
        if any(c.isalpha() and not c.isascii() for c in content):
            failures.append({"file": name, "issue": "Non-English script found"})
    return {"files_checked": count, "status": "passed" if not failures else "failed", "failures": failures}


if __name__ == "__main__":
    result = audit()
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["status"] == "passed" else 1)
