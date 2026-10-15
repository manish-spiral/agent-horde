# 013 — Feature 12: Long-term memory (first version)

## Goal

Let the agent remember facts across sessions (your preferences, project facts),
like Hermes Agent's persistent memory.

## Decision (simplest version first)

- A `remember(fact)` tool appends one line to `~/.horde/memory.md`.
- Every **new** conversation loads that file into the system prompt under
  "Things you remembered from earlier sessions", next to `AGENTS.md`
  ([011](011-project-instructions.md)). The terminal lists it under `instructions:`.
- **`remember` needs approval.** Memory influences every future session, so
  it's also a target for prompt injection (a malicious file telling the agent
  to "remember" something). You decide what's kept.
- The file is plain Markdown: you can read, edit or delete it yourself.

## What was done

```
src/horde/builtin_tools.py  remember tool, load_memory(), MEMORY_FILE
src/horde/cli.py            memory added to the new conversation's instructions
tests/conftest.py           tests never touch the real memory file
tests/test_memory.py        new: 2 tests
```

## How it was tested

`uv run pytest` gives **88 passed** (86 + 2 new). Verified that the real
`~/.horde/memory.md` was not created by the tests. Not yet exercised live.

## Known gaps

- Memory is loaded whole: fine for dozens of facts, not thousands. Search or
  retrieval comes later.
- There's no tool to forget or update a fact. Edit the file by hand.
