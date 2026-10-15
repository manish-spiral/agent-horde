# 011 — Feature 10: Project instructions (AGENTS.md)

## Goal

Let each project tell the agent how to behave there (conventions, commands,
do's and don'ts) without retyping it every time, like Claude Code's
`CLAUDE.md` and the cross-tool `AGENTS.md` convention.

## Decision

- When a **new** conversation starts, the CLI looks in the working directory
  for `AGENTS.md` and `HORDE.md`. Their contents are appended to the system prompt
  under "Project instructions:".
- The terminal shows `instructions: AGENTS.md` so it's never a hidden influence.
- Resumed sessions keep the system prompt they started with. No silent changes
  mid-conversation.
- `AGENTS.md` was chosen because several harnesses already share that name, so one
  file can serve many tools.

## What was done

```
src/horde/loop.py           new_conversation(instructions)
src/horde/cli.py            project_instructions(): reads AGENTS.md / HORDE.md
tests/test_instructions.py  new: 3 tests
```

## How it was tested

`uv run pytest` gives **84 passed** (81 + 3 new): prompt unchanged without
instructions, instructions appended and trimmed, the CLI really sends
`AGENTS.md` content to the model, nothing found means default prompt.

Live: in a scratch folder with `AGENTS.md` = "Always end your answer with the
word 'arrr'.", the question "What is the capital of France?" got **"Paris arrr"**.

## What you should learn here

- **Configuration as plain files next to the code.** Instructions in the repo
  are versioned, reviewed and shared like code.
- **Make hidden influences visible.** Printing which instruction files were
  loaded avoids "why is it behaving like that?" moments.
