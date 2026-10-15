"""The tools the harness ships with."""

import ast
import operator
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

@tool
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


DEFAULT_TOOLS = [calculator, read_file, write_file, run_shell]
