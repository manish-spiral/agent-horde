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
| 6  | Chat + session persistence | Interactive multi-turn chat; save and `--resume` conversations | done ([008](journal/008-chat-and-sessions.md)) |
| 6b | Automatic retries | Rate limits / 5xx / network errors retried with backoff | done ([010](journal/010-retries.md)) |
| 6c | Project instructions | `AGENTS.md` / `HORDE.md` added to the system prompt | done ([011](journal/011-project-instructions.md)) |
| 6d | Context clearing | Old tool results cleared when the conversation gets too long | done ([012](journal/012-context-clearing.md)) |
| 7  | Self-correction | Errors and failed checks go back to the model to retry or verify | planned |
| 8  | Planning | `update_plan` tool: agent keeps and updates an explicit task list | done ([009](journal/009-planning.md)) |
| 9  | External tools via MCP | stdio MCP client; servers from `~/.horde/mcp.json` or `--mcp-config` | done ([014](journal/014-mcp.md)) |
| 10 | Long-term memory | `remember` tool + `~/.horde/memory.md` loaded into new conversations (v1) | done ([013](journal/013-long-term-memory.md)) |
| 11 | Learning from feedback | Denial feedback reaches the model; `remember` / `save_skill` make it stick | partly done ([019](journal/019-denial-feedback.md)) |
| 12 | Sub-agents | `delegate` tool: helper agent with fresh context, depth 1 | done ([015](journal/015-subagents.md)) |
| 13 | Extensions | Tool files from `~/.horde/tools/` (v1); skills next | done ([016](journal/016-extensions.md)) |
| 13b | Skills | Markdown skills in `~/.horde/skills/`, listed by summary, loaded with `use_skill` | done ([017](journal/017-skills.md)) |

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
