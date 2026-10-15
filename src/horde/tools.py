"""Tools the agent can call.

A tool is a plain Python function plus a description and a JSON Schema for its
arguments. The model only ever sees the name, description and schema; the
harness is the one that actually runs the function.

The `@tool` decorator builds all of that from an ordinary typed function:

    @tool
    def add(a: int, b: Annotated[int, "the second number"]) -> str:
        '''Add two numbers.'''
        return str(a + b)
"""

import inspect
from dataclasses import dataclass
from typing import Annotated, Callable, get_args, get_origin, get_type_hints


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict  # JSON Schema describing the arguments
    function: Callable[..., str]
    # Ask the user before running it: always (True), never (False), or decided
    # per call by a function that looks at the arguments.
    needs_approval: bool | Callable[[dict], bool] = False

    def requires_approval(self, arguments: dict) -> bool:
        if not callable(self.needs_approval):
            return self.needs_approval
        try:
            return bool(self.needs_approval(arguments))
        except Exception:
            return True  # can't decide, so ask (fail closed)

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


def tool(function: Callable | None = None, *,
         needs_approval: bool | Callable[[dict], bool] = False):
    """Turn a typed, documented function into a Tool.

    Usable as `@tool` or `@tool(needs_approval=True)`.
    """
    def wrap(function: Callable) -> Tool:
        return Tool(
            name=function.__name__,
            description=inspect.getdoc(function) or "",
            parameters=_parameters_schema(function),
            function=function,
            needs_approval=needs_approval,
        )
    return wrap(function) if function else wrap


_JSON_TYPES = {str: "string", int: "integer", float: "number", bool: "boolean"}


def _parameters_schema(function: Callable) -> dict:
    hints = get_type_hints(function, include_extras=True)
    properties, required = {}, []
    for name, parameter in inspect.signature(function).parameters.items():
        hint, description = hints.get(name, str), None
        if get_origin(hint) is Annotated:
            hint, description = get_args(hint)[:2]
        if hint not in _JSON_TYPES:
            raise TypeError(f"{function.__name__}: unsupported type for '{name}': {hint}")
        properties[name] = {"type": _JSON_TYPES[hint]}
        if description:
            properties[name]["description"] = description
        if parameter.default is inspect.Parameter.empty:
            required.append(name)
    return {"type": "object", "properties": properties, "required": required}
