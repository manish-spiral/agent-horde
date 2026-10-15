# 007 — Feature 6: Coding tools (edit, list, search)

## Goal

Give the agent the core tools a coding agent like Claude Code relies on:
change part of a file, find files, and search their contents.

## Context

- The project owner asked for the harness to grow toward what Claude Code and
  Hermes Agent can do, one committed feature at a time, within a short session.
- Until now the agent could only rewrite whole files (`write_file`) or use
  `run_shell` with `grep`/`find`. Shell commands always ask for approval, and
  whole-file rewrites are risky and expensive in tokens.

## Options considered

| Question | Choice and why |
|----------|----------------|
| How to edit? | **Exact string replacement** (`old_text` → `new_text`), the approach Claude Code uses. The text must appear **exactly once**, so an edit can never hit the wrong place; a failed match returns an error the model can fix by including more context. Line-number edits break when lines shift; diffs/patches are hard for models to produce exactly. |
| Search: shell `grep` or a Python tool? | **Python tool**: works everywhere, skips `.git`/`.venv`/`node_modules`, caps output, and (being read-only) needs no approval inside the workspace. |
| Approval | `edit_file` always asks (it changes files). `list_files`/`search_files` follow `read_file`: free inside the workspace, ask outside it. |

## What was done

```
src/horde/builtin_tools.py   edit_file, list_files, search_files; DEFAULT_TOOLS updated
tests/test_coding_tools.py   new: 6 tests
```

- `_walk(root, pattern)` is shared by both read-only tools: glob, sorted,
  files only, skipping noise directories.
- Both cap results at 200 and say so when they cut off.
- `search_files` skips files it can't decode as text (binaries).
- `_path_outside_workspace` now defaults to `"."` when a tool's `path` argument
  is optional and omitted.

## How it was tested

`uv run pytest` gives **67 passed** (61 + 6 new): edit succeeds once, refuses 0 or 2
matches (file unchanged), edit needs approval, listing skips `.git`, glob
filtering, search output format, approval only outside the workspace.

Live (`groq:openai/gpt-oss-120b`): "Which Python files under src/ define a
class?" gave one `search_files` call with regex `^\s*class\s+`, then a
correct list of 9 files, in 2 steps, without any approval prompt.

## What you should learn here

- **Make edits unambiguous.** "Exactly one match" turns a dangerous operation
  into a safe one, and the error message tells the model how to fix its call.
- **Dedicated read-only tools beat a general shell** for common operations:
  they're safer (no approval needed), predictable, and cheaper in tokens.

## Next

Interactive multi-turn chat and session save/resume.
