import pytest


@pytest.fixture(autouse=True)
def isolated_runtime_data(tmp_path, monkeypatch):
    """Every test uses its own data directory; tests never touch the real runtime_data/."""
    monkeypatch.setenv("WORKWELL_DATA_DIR", str(tmp_path / "runtime_data"))
    return tmp_path / "runtime_data"
