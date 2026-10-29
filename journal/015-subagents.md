# 015 — Feature 14: Sub-agents (delegate)

## Goal

Let the agent hand a self-contained subtask to a helper agent, like Claude
Code's subagents. The main use is **context hygiene**: the helper does the
reading and searching in its own fresh conversation, and only its final answer
comes back.

## Decisions

| Question | Choice and why |
|----------|----------------|
| How? | A `delegate(task)` **tool** that calls `run_agent` again, so a helper is just another run of the same loop. No new machinery. |
| Context | **Fresh** conversation: the helper sees only the task text. The tool description tells the model to include every detail. |
| Tools | Same tools as the parent, **minus `delegate`**, so helpers can't spawn helpers without limit (depth 1). |
| Safety | Same approver as the parent: the helper's risky tools prompt you as usual. |
| Limits | The helper gets its own `max_steps` (20). Its failures (limits, errors) come back to the parent as `Error: …` text. |
| Observability | Helper events go to the same trace, tagged `"subagent": true`, and are shown indented with `↳`. |
| Wiring | `make_delegate_tool(model, tools, approve, on_event)` builds a tool *bound to this run*. It's a closure, because a tool function can't otherwise reach the model. |

## What was done

```
src/horde/subagents.py      new: make_delegate_tool()
src/horde/cli.py            delegate added to the agent's tools
src/horde/trace.py          sub-agent events indented with ↳
tests/test_subagents.py     new: 3 tests
```

## How it was tested

`uv run pytest` gives **96 passed** (93 + 3 new): the helper gets a fresh context
(only system + task), its answer returns as the tool result, its events are
tagged, a helper calling `delegate` gets "unknown tool", and the CLI offers
`delegate`.

Live (`groq:openai/gpt-oss-120b`): asked to delegate "find which file defines
`make_delegate_tool`", the parent wrote a detailed subtask, and the helper ran
`search_files` and found `src/horde/subagents.py`. Then **Groq's free daily
token limit (200k tokens/day) ran out** mid-run: HTTP 429 "try again in 4m31s".
The retry logic from [010](010-retries.md) waited and retried, then reported the
error clearly.

**Lesson from the live run:** retries cap their wait at 30 s, which suits
per-minute limits but not daily ones. A long `retry-after` should fail fast with
the message instead of waiting. That's a small follow-up.

## Known gaps

- Helpers run one at a time (no parallel helpers).
- No per-helper model choice (e.g. a cheaper model for searching).
- Helper token usage isn't added to the parent's `--max-tokens` budget.

## What you should learn here

- **Recursion is free when the loop is a function.** A sub-agent is just
  `run_agent` called from inside a tool.
- **Fresh context is the point.** Delegation keeps the main conversation small
  and focused.
- **Bound the recursion.** Leaving `delegate` out of the helper's tools is the
  simplest depth limit.
