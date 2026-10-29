import time

import pytest

from horde import cli
from horde.builtin_tools import is_inside_workspace, read_file
from horde.loop import TimeLimitReached, run_agent, run_tool
from horde.tools import tool


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    """A temporary working directory with a file inside it."""
    root = tmp_path / "workspace"
    root.mkdir()
    (root / "notes.txt").write_text("inside")
    (tmp_path / "secret.txt").write_text("outside")
    monkeypatch.chdir(root)
    return root


# --- workspace boundary -----------------------------------------------------

def test_workspace_boundary(workspace):
    assert is_inside_workspace("notes.txt")
    assert is_inside_workspace("sub/dir/new.txt")
    assert is_inside_workspace(str(workspace))
    assert not is_inside_workspace("../secret.txt")
    assert not is_inside_workspace("sub/../../secret.txt")
    assert not is_inside_workspace("/etc/passwd")


def test_symlink_pointing_outside_counts_as_outside(workspace):
    (workspace / "link.txt").symlink_to(workspace.parent / "secret.txt")
    assert not is_inside_workspace("link.txt")


def test_read_file_asks_only_outside_workspace(workspace):
    assert read_file.requires_approval({"path": "notes.txt"}) is False
    assert read_file.requires_approval({"path": "../secret.txt"}) is True


def test_reading_outside_is_denied_without_approval(workspace):
    tools = {"read_file": read_file}
    assert run_tool(tools, "read_file", '{"path": "notes.txt"}') == "inside"
    assert run_tool(tools, "read_file", '{"path": "../secret.txt"}') == \
        "Error: the user did not allow read_file to run"
    assert run_tool(tools, "read_file", '{"path": "../secret.txt"}',
                    lambda name, args: True) == "outside"


def test_approval_check_that_crashes_fails_closed():
    @tool(needs_approval=lambda arguments: arguments["missing"])
    def thing() -> str:
        """Example."""
        return "ran"

    assert thing.requires_approval({}) is True


# --- time limit -------------------------------------------------------------

class SlowModel:
    """Every call takes a while and asks for another calculation."""

    def complete(self, messages, tools):
        time.sleep(0.1)
        return {"role": "assistant", "content": None, "tool_calls": [{
            "id": "1", "type": "function",
            "function": {"name": "nothing", "arguments": "{}"}}]}, {}


def test_stops_at_time_limit():
    with pytest.raises(TimeLimitReached):
        run_agent("task", SlowModel(), [], max_steps=100, max_seconds=0.05)


# --- terminal approval ------------------------------------------------------

def answers(monkeypatch, *replies):
    queue = list(replies)
    monkeypatch.setattr("builtins.input", lambda: queue.pop(0))
    return queue


def test_terminal_approver_yes_and_no(monkeypatch):
    approve = cli.TerminalApprover()
    answers(monkeypatch, "y", "n", "")
    assert approve("run_shell", {"command": "ls"}) is True
    assert approve("run_shell", {"command": "ls"}) is False
    assert approve("run_shell", {"command": "ls"}) is False


def test_terminal_approver_always_is_per_tool(monkeypatch):
    approve = cli.TerminalApprover()
    remaining = answers(monkeypatch, "a", "n")
    assert approve("run_shell", {"command": "ls"}) is True
    assert approve("run_shell", {"command": "rm x"}) is True  # no prompt this time
    assert remaining == ["n"]
    assert approve("write_file", {"path": "x", "content": ""}) is False  # other tools still ask


def test_terminal_approver_denies_without_terminal(monkeypatch):
    def no_terminal():
        raise EOFError
    monkeypatch.setattr("builtins.input", no_terminal)
    assert cli.TerminalApprover()("run_shell", {"command": "ls"}) is False


# --- CLI exit codes ---------------------------------------------------------

def run_cli(monkeypatch, fake_model, *args):
    monkeypatch.setattr(cli, "create_model", lambda *args: fake_model)
    monkeypatch.setattr("sys.argv", ["horde", "task", *args])
    return cli.main()


def test_ctrl_c_exits_cleanly(monkeypatch, capsys):
    class InterruptedModel:
        def complete(self, messages, tools):
            raise KeyboardInterrupt

    assert run_cli(monkeypatch, InterruptedModel()) == 130
    assert "interrupted" in capsys.readouterr().err


def test_limit_is_reported_as_error(monkeypatch, capsys):
    assert run_cli(monkeypatch, SlowModel(), "--max-seconds", "0.05") == 1
    assert "error: no final answer after 0.05s" in capsys.readouterr().err


def test_setup_error_creates_no_trace(monkeypatch, capsys, private_trace_dir):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr("sys.argv", ["horde", "--provider", "anthropic", "task"])
    assert cli.main() == 1
    assert "ANTHROPIC_API_KEY is not set" in capsys.readouterr().err
    assert not private_trace_dir.exists()


def test_typed_feedback_denies_and_reaches_the_model(monkeypatch):
    answers(monkeypatch, "No, use list_files instead")
    approve = cli.TerminalApprover()
    assert approve("run_shell", {"command": "ls"}) == "No, use list_files instead"

    @tool(needs_approval=True)
    def run_it() -> str:
        """Needs approval."""
        return "ran"

    result = run_tool({"run_it": run_it}, "run_it", "{}", lambda n, a: "use the other tool")
    assert result == "Error: the user did not allow run_it to run. They said: use the other tool"
