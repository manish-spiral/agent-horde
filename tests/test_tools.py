from typing import Annotated

import pytest

from horde.builtin_tools import read_file, run_shell, write_file
from horde.tools import tool


def test_tool_decorator_builds_schema_from_function():
    @tool
    def greet(name: Annotated[str, "who to greet"], times: int = 1, loud: bool = False) -> str:
        """Greet someone."""
        return name * times

    assert greet.name == "greet"
    assert greet.description == "Greet someone."
    assert greet.needs_approval is False
    assert greet.parameters == {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "who to greet"},
            "times": {"type": "integer"},
            "loud": {"type": "boolean"},
        },
        "required": ["name"],
    }
    assert greet.function("hi", times=2) == "hihi"


def test_tool_decorator_rejects_unsupported_types():
    with pytest.raises(TypeError, match="unsupported type for 'items'"):
        @tool
        def bad(items: list) -> str:
            """Not supported yet."""
            return ""


def test_only_side_effect_tools_need_approval():
    assert read_file.needs_approval is False
    assert write_file.needs_approval is True
    assert run_shell.needs_approval is True


def test_write_then_read_file(tmp_path):
    path = tmp_path / "nested" / "note.txt"
    assert write_file.function(str(path), "hello") == f"Wrote 5 characters to {path}"
    assert read_file.function(str(path)) == "hello"


def test_read_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        read_file.function("/definitely/not/here.txt")


def test_run_shell_reports_exit_code_and_output():
    result = run_shell.function("echo out; echo err >&2; exit 3")
    assert result == "exit code: 3\nstdout:\nout\n\nstderr:\nerr\n"


def test_run_shell_times_out():
    assert run_shell.function("sleep 5", timeout=1) == "Error: command timed out after 1s"
