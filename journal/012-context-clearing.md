# 012 — Feature 11: Keeping long conversations inside the context window

## Goal

Stop long chats and long tasks from growing until they overflow the model's
context window. This was the top gap after [008](008-chat-and-sessions.md).

## Decision (simplest version first)

Before each model call, if the conversation exceeds **200,000 characters**
(~50k tokens), every tool result except the newest **5** is replaced with
`[old tool result cleared to save context]`.

- Tool results (file contents, command output, search results) are usually the
  bulk of a conversation, and old ones are rarely needed again. The model
  can re-read a file if it does need it.
- User messages, the model's replies and tool *calls* are kept, so the
  conversation still makes sense.
- A `context_cleared` event goes to the trace and the terminal.
- Considered: **summarising** old turns with an extra model call. That's better
  for very long chats but costs tokens and needs care. It's the next step if
  clearing isn't enough.

## What was done

```
src/horde/loop.py      clear_old_tool_results(); called before each model call
src/horde/trace.py     shows context_cleared events
tests/test_context.py  new: 2 tests
```

## How it was tested

`uv run pytest` gives **86 passed** (84 + 2 new): small conversations untouched;
past the limit, all but the newest results cleared and nothing else touched;
already-cleared results aren't counted twice. Not exercised live (it needs a
very long conversation).

## Known gaps

- **Anthropic preserved thinking:** current Claude models check that earlier
  turns aren't edited. Clearing old tool results *is* an edit, so on those models a
  very long conversation could be rejected once clearing kicks in. Claude-specific
  handling (or Anthropic's server-side context editing) is a follow-up.
- Limits are in characters, not real tokens, and the same for every model.

## What you should learn here

- **Context is a budget.** Everything in the history is resent on every call.
- **Drop the bulkiest, least-needed data first**: old tool output, then
  consider summarising.
