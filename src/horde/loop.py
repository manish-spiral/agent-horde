"""The agent loop: think -> act -> observe -> repeat.

`model` is anything with a `complete(messages, tools) -> (message, usage)`
method (see horde.models.base.Model). That is the whole contract, which is
why tests can use a fake model.

Everything that happens is reported as an event (a plain dict) to `on_event`,
so callers can print it, save it to a trace, or ignore it.
"""

import json
import time
from collections import Counter
from typing import Callable

from horde.tools import Tool

SYSTEM_PROMPT = (
    "You are a helpful agent. Use the available tools when they help. "
    "For tasks with several steps, keep a plan with update_plan and update it as you go. "
    "When you have the final answer, reply without calling any tool."
)

# Tool results go back into the conversation, which is resent on every step.
# Cap them so one huge file or command output can't flood the context.
MAX_RESULT_CHARS = 20_000

TOKEN_KEYS = ("prompt_tokens", "completion_tokens", "total_tokens")

# Decides whether a tool that needs approval may run: (tool name, arguments) -> yes/no.
Approver = Callable[[str, dict], bool]


def deny_all(name: str, arguments: dict) -> bool:
    return False


class LimitReached(Exception):
    outcome = "limit"


class StepLimitReached(LimitReached):
    outcome = "step_limit"


class TimeLimitReached(LimitReached):
    outcome = "time_limit"


class TokenLimitReached(LimitReached):
    outcome = "token_limit"


def new_conversation() -> list[dict]:
    return [{"role": "system", "content": SYSTEM_PROMPT}]


def run_agent(task: str, model, tools: list[Tool], max_steps: int = 10,
              max_seconds: float | None = None, max_tokens: int | None = None,
              approve: Approver = deny_all,
              on_event: Callable[[dict], None] = lambda _: None,
              messages: list[dict] | None = None) -> str:
    """Work on `task` until there's an answer.

    Pass `messages` to continue an earlier conversation: the task and
    everything that happens are appended to that same list.
    """
    tools_by_name = {tool.name: tool for tool in tools}
    schemas = [tool.schema() for tool in tools]
    if messages is None:
        messages = new_conversation()
    messages.append({"role": "user", "content": task})
    started = time.monotonic()
    usage = Counter(dict.fromkeys(TOKEN_KEYS, 0))
    model_calls = 0

    def emit(event_type: str, **fields):
        on_event({"type": event_type, "elapsed": round(time.monotonic() - started, 3), **fields})

    emit("run_start", task=task, model=getattr(model, "name", type(model).__name__),
         tools=list(tools_by_name),
         limits={"max_steps": max_steps, "max_seconds": max_seconds, "max_tokens": max_tokens})
    try:
        for step in range(1, max_steps + 1):
            if max_seconds is not None and time.monotonic() - started >= max_seconds:
                raise TimeLimitReached(f"no final answer after {max_seconds}s")
            if max_tokens is not None and usage["total_tokens"] >= max_tokens:
                raise TokenLimitReached(
                    f"used {usage['total_tokens']} of {max_tokens} tokens without a final answer")

            # Think: ask the model what to do next.
            call_started = time.monotonic()
            reply, reply_usage = model.complete(messages, schemas)
            model_calls += 1
            usage.update({key: reply_usage.get(key) or 0 for key in TOKEN_KEYS})
            tool_calls = reply.get("tool_calls") or []
            message = {"role": "assistant", "content": reply.get("content")}
            if tool_calls:
                message["tool_calls"] = tool_calls
            if reply.get("provider_state"):  # opaque data the adapter needs back
                message["provider_state"] = reply["provider_state"]
            messages.append(message)
            emit("model_call", step=step, duration=round(time.monotonic() - call_started, 3),
                 usage=reply_usage, message=message)

            # No tool call means the model is done.
            if not tool_calls:
                answer = reply.get("content") or ""
                emit("run_end", outcome="answer", answer=answer, steps=model_calls, usage=dict(usage))
                return answer

            # Act + observe: run each requested tool and feed the result back.
            for call in tool_calls:
                result, approval, duration = _run_recorded(tools_by_name, call, approve)
                emit("tool_call", step=step, id=call["id"], name=call["function"]["name"],
                     arguments=call["function"]["arguments"], approval=approval,
                     result=result, duration=duration)
                messages.append({"role": "tool", "tool_call_id": call["id"], "content": result})

        raise StepLimitReached(f"no final answer after {max_steps} steps")
    except BaseException as error:
        outcome = getattr(error, "outcome",
                          "interrupted" if isinstance(error, KeyboardInterrupt) else "error")
        emit("run_end", outcome=outcome, error=str(error) or type(error).__name__,
             steps=model_calls, usage=dict(usage))
        raise


def _run_recorded(tools_by_name: dict[str, Tool], call: dict,
                  approve: Approver) -> tuple[str, str, float]:
    """Run one tool call, also reporting whether approval was needed and given."""
    decision = {}

    def approve_and_remember(name: str, arguments: dict) -> bool:
        decision["approved"] = approve(name, arguments)
        return decision["approved"]

    started = time.monotonic()
    result = run_tool(tools_by_name, call["function"]["name"],
                      call["function"]["arguments"], approve_and_remember)
    if not decision:
        approval = "not_needed"
    else:
        approval = "approved" if decision["approved"] else "denied"
    return result, approval, round(time.monotonic() - started, 3)


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
