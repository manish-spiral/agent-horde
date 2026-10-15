"""The tools the harness ships with."""

import ast
import operator
import re
import subprocess
from pathlib import Path
from typing import Annotated

from horde.tools import tool

# --- calculator -------------------------------------------------------------
# Never eval() text that came from a model. We parse the expression into a
# syntax tree and only allow numbers and arithmetic operators.

_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _evaluate(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _evaluate(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPERATORS:
        return _OPERATORS[type(node.op)](_evaluate(node.left), _evaluate(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPERATORS:
        return _OPERATORS[type(node.op)](_evaluate(node.operand))
    raise ValueError(f"unsupported expression: {ast.dump(node)}")


def calculate(expression: str) -> str:
    return str(_evaluate(ast.parse(expression, mode="eval")))


@tool
def calculator(expression: Annotated[str, "The expression, e.g. '17 * 23 + 5'"]) -> str:
    """Evaluate an arithmetic expression. Supports + - * / // % ** and parentheses."""
    return calculate(expression)


# --- files ------------------------------------------------------------------
# The working directory is the agent's workspace. Reading inside it is free;
# touching anything outside it needs the user's approval.

def is_inside_workspace(path: str) -> bool:
    """True if `path` resolves (following symlinks and '..') to inside the working directory."""
    return Path(path).resolve().is_relative_to(Path.cwd().resolve())


def _path_outside_workspace(arguments: dict) -> bool:
    return not is_inside_workspace(arguments.get("path", "."))


@tool(needs_approval=_path_outside_workspace)
def read_file(path: Annotated[str, "File path, relative to the working directory or absolute"]) -> str:
    """Read a text file and return its contents."""
    return Path(path).read_text(encoding="utf-8", errors="replace")


@tool(needs_approval=True)
def write_file(
    path: Annotated[str, "File path, relative to the working directory or absolute"],
    content: Annotated[str, "The full new content of the file"],
) -> str:
    """Create or overwrite a text file. Parent directories are created if needed."""
    file = Path(path)
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(content, encoding="utf-8")
    return f"Wrote {len(content)} characters to {path}"


@tool(needs_approval=True)
def edit_file(
    path: Annotated[str, "File to edit"],
    old_text: Annotated[str, "Exact text to replace; must appear exactly once"],
    new_text: Annotated[str, "Replacement text"],
) -> str:
    """Replace one exact piece of text in a file. Safer than rewriting the whole file."""
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    count = text.count(old_text)
    if count != 1:
        raise ValueError(f"old_text must appear exactly once, found {count} times; "
                         "include more surrounding lines to make it unique")
    file.write_text(text.replace(old_text, new_text), encoding="utf-8")
    return f"Edited {path}"


# Directories that are never worth searching.
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", "dist"}
MAX_MATCHES = 200


def _walk(root: Path, pattern: str):
    for file in sorted(root.glob(pattern)):
        if file.is_file() and not SKIP_DIRS & set(file.relative_to(root).parts):
            yield file


@tool(needs_approval=_path_outside_workspace)
def list_files(
    pattern: Annotated[str, "Glob pattern, e.g. '**/*.py' (default: all files)"] = "**/*",
    path: Annotated[str, "Directory to search (default: working directory)"] = ".",
) -> str:
    """List files matching a glob pattern, skipping .git, .venv, node_modules and caches."""
    files = [str(file) for file in _walk(Path(path), pattern)]
    shown = files[:MAX_MATCHES]
    more = f"\n[{len(files) - MAX_MATCHES} more files]" if len(files) > MAX_MATCHES else ""
    return "\n".join(shown) + more if files else "No files found"


@tool(needs_approval=_path_outside_workspace)
def search_files(
    regex: Annotated[str, "Regular expression to search for"],
    path: Annotated[str, "Directory to search (default: working directory)"] = ".",
    pattern: Annotated[str, "Only search files matching this glob (default: all)"] = "**/*",
) -> str:
    """Search file contents with a regular expression. Returns file:line: text for each match."""
    compiled = re.compile(regex)
    matches = []
    for file in _walk(Path(path), pattern):
        try:
            lines = file.read_text(encoding="utf-8").splitlines()
        except (UnicodeDecodeError, OSError):
            continue  # binary or unreadable
        for number, line in enumerate(lines, 1):
            if compiled.search(line):
                matches.append(f"{file}:{number}: {line.strip()[:200]}")
                if len(matches) >= MAX_MATCHES:
                    return "\n".join(matches) + f"\n[stopped at {MAX_MATCHES} matches]"
    return "\n".join(matches) or "No matches"


# --- planning ---------------------------------------------------------------
# The plan lives in the conversation itself: the model sends the whole list each
# time, and the latest tool result is the current plan. No hidden state.

PLAN_MARKS = ("[ ]", "[~]", "[x]")


@tool
def update_plan(
    plan: Annotated[str, "The whole task list, one item per line, each starting with "
                         "[ ] (to do), [~] (in progress) or [x] (done)"],
) -> str:
    """Write down or update your step-by-step plan for a multi-step task.
    Send the complete list every time; mark items done as you finish them."""
    items = [line.strip() for line in plan.splitlines() if line.strip()]
    if not items or not all(item.startswith(PLAN_MARKS) for item in items):
        raise ValueError("every line must start with [ ], [~] or [x]")
    done = sum(item.startswith("[x]") for item in items)
    return f"Plan updated ({done}/{len(items)} done):\n" + "\n".join(items)


# --- long-term memory -------------------------------------------------------
# Facts saved here are loaded into every new conversation.

MEMORY_FILE = Path.home() / ".horde" / "memory.md"


@tool(needs_approval=True)  # memory shapes every future session: the user decides
def remember(fact: Annotated[str, "One short fact worth knowing in future conversations"]) -> str:
    """Save a fact to long-term memory (e.g. user preferences, project facts)."""
    MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with MEMORY_FILE.open("a", encoding="utf-8") as file:
        file.write(f"- {' '.join(fact.split())}\n")
    return "Remembered."


def load_memory() -> str | None:
    if not MEMORY_FILE.is_file():
        return None
    return MEMORY_FILE.read_text(encoding="utf-8").strip() or None


# --- shell ------------------------------------------------------------------

@tool(needs_approval=True)
def run_shell(
    command: Annotated[str, "The shell command to run"],
    timeout: Annotated[int, "Seconds before the command is stopped (default 60)"] = 60,
) -> str:
    """Run a shell command in the working directory. Returns exit code, stdout and stderr."""
    try:
        completed = subprocess.run(command, shell=True, capture_output=True, text=True,
                                   timeout=timeout, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return f"Error: command timed out after {timeout}s"
    return (f"exit code: {completed.returncode}\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}")


DEFAULT_TOOLS = [calculator, read_file, write_file, edit_file, list_files, search_files,
                 update_plan, remember, run_shell]
