"""Sub-agents: the agent hands a self-contained subtask to a helper agent.

The helper runs the same loop with a *fresh* conversation, so the subtask's
reading and searching doesn't fill up the main agent's context. Only the
helper's final answer comes back, as the tool result.
"""

from typing import Annotated, Callable

from horde.loop import Approver, run_agent
from horde.tools import Tool, tool


def make_delegate_tool(model, tools: list[Tool], approve: Approver,
                       on_event: Callable[[dict], None], max_steps: int = 20) -> Tool:
    """Build a `delegate` tool bound to this run's model, tools, approver and events.

    `tools` should not include `delegate` itself, so helpers can't spawn
    helpers without limit.
    """

    @tool
    def delegate(task: Annotated[str, "The subtask, fully self-contained: include every detail "
                                      "the helper needs, since it can't see this conversation"]) -> str:
        """Hand a self-contained subtask (research, searching, a side job) to a helper agent
        with a fresh context and the same tools. Returns the helper's final answer."""
        return run_agent(task, model, tools, max_steps=max_steps, approve=approve,
                         on_event=lambda event: on_event({**event, "subagent": True}))

    return delegate
