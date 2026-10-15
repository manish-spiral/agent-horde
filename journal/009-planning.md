# 009 — Feature 8: Planning (a task list the agent keeps)

## Goal

Let the agent write down a step-by-step plan for multi-step tasks and tick
items off as it goes, like Claude Code's to-do list. This makes long tasks
more reliable and visible.

## The big idea: the plan lives in the conversation

There is **no hidden plan object**. The model calls `update_plan` with the
*whole* list every time; the tool checks the format and echoes it back with a
progress count. Because tool results stay in the message list, the latest
result *is* the current plan. It's saved with the session and shown in the trace
for free.

## Options considered

| Option | Why not / why |
|--------|---------------|
| Planner step before the loop (a separate "make a plan" model call) | Adds a fixed phase and cost to every task, even trivial ones |
| Plan stored in harness state, with add/complete tools | More tools and state for the model to keep in sync |
| **One tool, whole list each time, state in the conversation** | Simplest; the model decides *when* a plan is worth it; nothing to get out of sync |

Format: one item per line, starting with `[ ]` to do, `[~]` in progress or
`[x]` done. Anything else is rejected with an error the model can fix.

The system prompt now says: *"For tasks with several steps, keep a plan with
update_plan and update it as you go."*

## What was done

```
src/horde/builtin_tools.py  update_plan tool (no approval: it has no side effects)
src/horde/loop.py           system prompt mentions planning
tests/test_planning.py      new: 5 tests
```

## How it was tested

`uv run pytest` gives **76 passed** (71 + 5 new): progress count, blank lines and
indentation ignored, unmarked lines rejected, tool registered, no approval.

Live (`groq:openai/gpt-oss-120b`): "count Python files under src/, count
test files, add them" gave `update_plan` (0/3), `list_files` ×2, `calculator("13 + 9")`,
then `update_plan` (3/3), and the answer **22**, which is correct (13 + 9).

**Observation:** the model ticked everything off at the end, not after each step.
The prompt says "update it as you go" but models follow that loosely. Stronger
nudges (e.g. reminding the model of open items) are a possible later improvement.

## What you should learn here

- **Put state where the model can see it.** A plan in the conversation needs
  no syncing, and is persisted and traced automatically.
- **Let the model decide when to plan.** A tool plus one prompt line costs
  nothing on simple tasks.
- **Validate tool input and explain errors**, so the model can fix its own call.

## Next

Context compaction, MCP tool servers, long-term memory, sub-agents, extensions.
