"""The agent loop: think -> act -> observe -> repeat.

`model` is anything with a `complete(messages, tools) -> message` method.
That is the whole contract, which is why tests can use a fake model.
"""

import json
import time
from typing import Callable

from horde.tools import Tool

SYSTEM_PROMPT = (
    "You are a helpful agent. Use the available tools when they help. "
    "When you have the final answer, reply without calling any tool."
)

# Tool results go back into the conversation, which is resent on every step.
# Cap them so one huge file or command output can't flood the context.
MAX_RESULT_CHARS = 20_000

# Decides whether a tool that needs approval may run: (tool name, arguments) -> yes/no.
Approver = Callable[[str, dict], bool]


def deny_all(name: str, arguments: dict) -> bool:
    return False


class LimitReached(Exception):
    pass


class StepLimitReached(LimitReached):
    pass


class TimeLimitReached(LimitReached):
    pass


def run_agent(task: str, model, tools: list[Tool], max_steps: int = 10,
              max_seconds: float | None = None,
              approve: Approver = deny_all,
              log: Callable[[str], None] = lambda _: None) -> str:
    tools_by_name = {tool.name: tool for tool in tools}
    schemas = [tool.schema() for tool in tools]
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": task},
    ]
    started = time.monotonic()

    for step in range(1, max_steps + 1):
        if max_seconds is not None and time.monotonic() - started >= max_seconds:
            raise TimeLimitReached(f"no final answer after {max_seconds}s")

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
            result = run_tool(tools_by_name, name, arguments, approve)
            log(f"[step {step}] {name}({arguments}) -> {result}")
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": result})

    raise StepLimitReached(f"no final answer after {max_steps} steps")


def run_tool(tools_by_name: dict[str, Tool], name: str, arguments: str,
             approve: Approver = deny_all) -> str:
    """Run one tool call. Errors become text so the model can see and react to them."""
    tool = tools_by_name.get(name)
    if tool is None:
        return f"Error: unknown tool '{name}'"
    try:
        parsed = json.loads(arguments or "{}")
    except json.JSONDecodeError as error:
        return f"Error: arguments are not valid JSON: {error}"
    if not isinstance(parsed, dict):
        return "Error: arguments must be a JSON object"
    if tool.requires_approval(parsed) and not approve(name, parsed):
        return f"Error: the user did not allow {name} to run"
    try:
        result = str(tool.function(**parsed))
    except Exception as error:
        return f"Error: {type(error).__name__}: {error}"
    if len(result) > MAX_RESULT_CHARS:
        hidden = len(result) - MAX_RESULT_CHARS
        result = result[:MAX_RESULT_CHARS] + f"\n[truncated: {hidden} more characters]"
    return result
