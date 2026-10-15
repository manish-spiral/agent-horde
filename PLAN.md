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
| 2  | Tool interface + basic tools | Adding a tool is trivial; read/write files, run shell (with approval) | done ([003](journal/003-tools.md)) |
| 3  | Control & safety | Workspace boundary, "always allow", time limit, clean Ctrl+C | done ([004](journal/004-control-and-safety.md)) |
| 4  | Observability | Events + JSONL trace of every step; token budget; `horde-trace show/replay` | done ([005](journal/005-observability.md)) |
| 5  | All major model providers | 3 adapters (OpenAI-format, Anthropic, Gemini), 13 providers, `Model` protocol | done ([006](journal/006-model-providers.md)) |
| 5b | Coding tools | `edit_file`, `list_files`, `search_files` | done ([007](journal/007-coding-tools.md)) |
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
| Model providers | Groq default; 13 providers via 3 API formats | [journal/001](journal/001-language-choice.md), [journal/006](journal/006-model-providers.md) |
| Internal message format | OpenAI chat format + opaque `provider_state` | [journal/006](journal/006-model-providers.md) |
| Implementation language | Python 3.12 | [journal/001](journal/001-language-choice.md) |
| Git | Claude commits and pushes to `main` after asking each time | [journal/000](journal/000-project-kickoff.md) |
| Default model | `openai/gpt-oss-120b` on Groq | [journal/003](journal/003-tools.md) |
| Trace location | `~/.horde/traces/`, JSON Lines | [journal/005](journal/005-observability.md) |

## How we work

1. Propose the next step and get approval.
2. Build one small feature.
3. Test it.
4. Document it in `journal/`.
5. Ask, then commit and push. Ask before the next feature.
