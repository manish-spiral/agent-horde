# Agent Horde — Plan

## Intent

A harness that can take any task and work on it until it's done, using whatever
model and tools it is given — while staying observable and under human control,
and growing new abilities without rewriting what already exists.

## Principles

- **Small core, everything else plugs in.** The core is only the loop:
  think → act → observe → repeat. Models, tools, memory and policies attach to it.
- **One new ability per feature.** Each feature is tested and documented before the next starts.
- **Safe by default.** Anything with side effects can be gated, limited and stopped.
- **Every step is visible.** You can always see what the harness did and why.
- **No speculative abstraction.** An abstraction is added only when a second real use needs it.
- **Open to any language.** Tools and extensions talk to the core over plain
  protocols (JSON, MCP), so they can be written in any language.

## Roadmap

The order is a proposal and will change as we learn.

| #  | Feature | What it unlocks | Status |
|----|---------|-----------------|--------|
| 1  | Core agent loop | Model gets a task, calls a tool, sees the result, loops until done, with a CLI. Tested with a fake model. | done ([002](journal/002-core-loop.md)) |
| 2  | Tool interface + basic tools | Adding a tool is trivial; read/write files, run shell | planned |
| 3  | Control & safety | Approve/deny tool calls, step and cost limits, interrupt | planned |
| 4  | Observability | Structured trace of every step; inspect and replay | planned |
| 5  | Second model provider | Proves "any model"; the model abstraction is introduced here | planned |
| 6  | Session persistence | Save and resume conversations | planned |
| 7  | Self-correction | Errors and failed checks go back to the model to retry or verify | planned |
| 8  | Planning | Agent keeps and updates an explicit task list | planned |
| 9  | External tools via MCP | Connect to any tool server | planned |
| 10 | Long-term memory | Facts that persist across sessions | planned |
| 11 | Learning from feedback | Corrections are saved and shape later behavior | planned |
| 12 | Sub-agents | Agent delegates subtasks to other agents | planned |
| 13 | Extensions | Load skills, tools and policies from a directory | planned |

Beyond 13: no fixed ceiling — new features are proposed as needs appear.

## Decisions so far

| Decision | Choice | Where explained |
|----------|--------|-----------------|
| First model provider | Groq | [journal/001](journal/001-language-choice.md) |
| Implementation language | Python 3.12 | [journal/001](journal/001-language-choice.md) |
| Git | Handled by the project owner | [journal/000](journal/000-project-kickoff.md) |

## How we work

1. Propose the next step and get approval.
2. Build one small feature.
3. Test it.
4. Document it in `journal/`.
5. Hand over for commit, then ask before the next feature.
