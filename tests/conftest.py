import pytest

from horde import builtin_tools, cli


@pytest.fixture(autouse=True)
def private_trace_dir(tmp_path, monkeypatch):
    """Never let a test write traces or sessions into the real ~/.horde."""
    monkeypatch.setattr(cli, "DEFAULT_TRACE_DIR", tmp_path / "traces")
    monkeypatch.setattr(cli, "DEFAULT_SESSION_DIR", tmp_path / "sessions")
    monkeypatch.setattr(builtin_tools, "MEMORY_FILE", tmp_path / "memory.md")
    return tmp_path / "traces"


@pytest.fixture
def private_session_dir(tmp_path):
    return tmp_path / "sessions"
