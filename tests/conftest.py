import pytest

from horde import cli


@pytest.fixture(autouse=True)
def private_trace_dir(tmp_path, monkeypatch):
    """Never let a test write traces into the real ~/.horde."""
    monkeypatch.setattr(cli, "DEFAULT_TRACE_DIR", tmp_path / "traces")
    return tmp_path / "traces"
