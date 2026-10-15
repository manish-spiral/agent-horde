# 008 — Feature 7: Interactive chat and saved sessions

## Goal

Talk to the agent over many turns, like Claude Code or Hermes Agent, and pick
up a conversation later with `--resume`.

## Context

Until now every `horde "task"` started from nothing. Real work is a
conversation: "now also do X", "that's wrong, try Y".

## The big idea

The model is stateless (see [002](002-core-loop.md)): the *harness* remembers by
keeping the message list. So a multi-turn chat is just **reusing the same list
across calls**, and resuming a session is just **saving that list to disk and
loading it again**.

## Options considered

| Question | Choice and why |
|----------|----------------|
| How does the loop continue a conversation? | `run_agent(..., messages=list)` appends to the caller's list. No new class; the CLI owns the list. |
| Session format | **One JSON file per session**, the full message list, rewritten after every turn. Simple, readable, and exactly what the loop needs. (The trace is the *event log*; the session is the *conversation state*. They're separate on purpose.) |
| Writing safely | Write to `.tmp`, then `replace()`. Renaming is atomic, so a crash never leaves half a session. |
| Where | `~/.horde/sessions/` (private, mode 700), next to traces. `--session-dir` overrides it. |
| Chat input | No task argument means chat mode. Lines are read until `exit`, `quit` or end of input; empty lines are ignored. |
| Errors in chat | A failed turn (limit, API error) prints the error and the chat continues. Ctrl+C ends the chat, but the session is still saved. |
| "Always allow" in chat | One `TerminalApprover` per session, so "always" lasts for the whole chat. |

## What was done

```
src/horde/session.py     new: new_session_id, save_session (atomic), load_session ("last")
src/horde/loop.py        new_conversation(); run_agent(messages=...) continues a conversation
src/horde/cli.py         optional task; chat mode; --resume; --session-dir; session saved every turn
tests/conftest.py        tests also never write sessions to the real ~/.horde
tests/test_session.py    new: 4 tests
```

## How it was tested

`uv run pytest` gives **71 passed** (67 + 4 new): save/load and "last", a conversation
continued across two `run_agent` calls, chat mode with typed input (context
kept, empty line skipped, `exit` ends it, session file written), and
`--resume last` adds to the same session file.

**Mistake caught:** the first test run, before `conftest.py` redirected the
session directory, wrote 3 placeholder sessions into the real
`~/.horde/sessions`. They were checked (content "task"), deleted, and the
redirect was added. A new CLI side effect needs its test isolation in the same
change.

**Live** (`groq:openai/gpt-oss-120b`, input piped in):
1. "My lucky number is 17. Just say ok." gave "Ok."
2. "What is my lucky number times 3? Use the calculator." gave **51** (context kept).
3. `horde --resume last "What was my lucky number?"` gave **17** (loaded from disk).

## Known gaps

- **Context grows forever.** Long chats will eventually exceed the model's
  context window. That needs summarising or trimming (compaction).
- **No session list command.** Only `--resume last` or an exact id.
- **`horde-trace replay`** replays only the first turn of a multi-turn trace.

## What you should learn here

- **Memory in a chat is just the message list.** The model remembers nothing;
  the harness resends everything.
- **Separate state from log.** The session (what the model sees next time) and
  the trace (what happened) answer different questions.
- **Atomic writes**: write a temp file, then rename, for any file you overwrite.
- **Every new side effect needs test isolation**, added in the same change.

## Next

Context compaction, MCP tool servers, long-term memory, sub-agents.
