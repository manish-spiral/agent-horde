"""The agent loop: think -> act -> observe -> repeat.

`model` is anything with a `complete(messages, tools) -> message` method.
That is the whole contract, which is why tests can use a fake model.
"""

import json
from typing import Callable

from horde.tools import Tool

SYSTEM_PROMPT = (
    "You are a helpful agent. Use the available tools when they help. "
    "When you have the final answer, reply without calling any tool."
)


class StepLimitReached(Exception):
    pass


def run_agent(task: str, model, tools: list[Tool], max_steps: int = 10,
              log: Callable[[str], None] = lambda _: None) -> str:
    tools_by_name = {tool.name: tool for tool in tools}
    schemas = [tool.schema() for tool in tools]
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": task},
    ]

    for step in range(1, max_steps + 1):
        # Think: ask the model what to do next.
        reply = model.complete(messages, schemas)
        tool_calls = reply.get("tool_calls") or []
        messages.append({"role": "assistant", "content": reply.get("content"),
                         **({"tool_calls": tool_calls} if tool_calls else {})})

        # No tool call means the model is done.
        if not tool_calls:
            log(f"[step {step}] final answer")
            return reply.get("content") or ""

        # Act + observe: run each requested tool and feed the result back.
        for call in tool_calls:
            name = call["function"]["name"]
            arguments = call["function"]["arguments"]
            result = run_tool(tools_by_name, name, arguments)
            log(f"[step {step}] {name}({arguments}) -> {result}")
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": result})

    raise StepLimitReached(f"no final answer after {max_steps} steps")


def run_tool(tools_by_name: dict[str, Tool], name: str, arguments: str) -> str:
    """Run one tool call. Errors become text so the model can see and react to them."""
    tool = tools_by_name.get(name)
    if tool is None:
        return f"Error: unknown tool '{name}'"
    try:
        return str(tool.function(**json.loads(arguments or "{}")))
    except Exception as error:
        return f"Error: {type(error).__name__}: {error}"
