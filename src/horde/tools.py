"""Tools the agent can call.

A tool is a plain Python function plus a description and a JSON Schema for its
arguments. The model only ever sees the name, description and schema; the
harness is the one that actually runs the function.
"""

import ast
import operator
from dataclasses import dataclass
from typing import Callable


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict  # JSON Schema describing the arguments
    function: Callable[..., str]

    def schema(self) -> dict:
        """The tool description in the format chat-completions APIs expect."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


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


calculator = Tool(
    name="calculator",
    description="Evaluate an arithmetic expression, e.g. '17 * 23 + 5'. "
    "Supports + - * / // % ** and parentheses.",
    parameters={
        "type": "object",
        "properties": {
            "expression": {"type": "string", "description": "The expression to evaluate"}
        },
        "required": ["expression"],
    },
    function=calculate,
)
