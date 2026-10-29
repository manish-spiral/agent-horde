import pytest

from horde import cli
from horde.extensions import load_tool_files
from test_loop import FakeModel, answer, tool_call

GREET = '''
from horde.tools import tool

@tool
def greet(name: str) -> str:
    """Greet someone."""
    return f"hello {name}"

not_a_tool = 42
'''


def test_tools_are_loaded_from_files(tmp_path):
    (tmp_path / "greet.py").write_text(GREET)
    [greet] = load_tool_files(tmp_path)
    assert greet.name == "greet" and greet.function("ana") == "hello ana"


def test_missing_folder_means_no_extensions(tmp_path):
    assert load_tool_files(tmp_path / "none") == []


def test_broken_file_is_a_clear_error(tmp_path):
    (tmp_path / "bad.py").write_text("this is not python")
    with pytest.raises(RuntimeError, match="bad.py failed to load"):
        load_tool_files(tmp_path)


def test_cli_gives_extension_tools_to_the_agent(tmp_path, monkeypatch):
    (tmp_path / "greet.py").write_text(GREET)
    fake = FakeModel([tool_call("greet", {"name": "ana"}), answer("done")])
    monkeypatch.setattr(cli, "create_model", lambda *args: fake)
    monkeypatch.setattr("sys.argv", ["horde", "--tools-dir", str(tmp_path), "task"])
    assert cli.main() == 0
    assert fake.received[1][-1]["content"] == "hello ana"
