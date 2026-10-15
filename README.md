# Agent Horde

A general, extensible agent harness, built one small feature at a time as a
learning project.

- **[PLAN.md](PLAN.md)**: intent, principles, roadmap
- **[journal/](journal/)**: a step-by-step log of every decision and feature

## Setup

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync                 # create .venv and install everything
uv run pytest           # run the tests (no API key needed)
```

## Run

Get a free API key from <https://console.groq.com>, then:

```bash
export GROQ_API_KEY=...
uv run horde "what is 17 * 23 + 5?"
```

Run `horde` with no task for an interactive chat (type `exit` to leave).
Every conversation is saved to `~/.horde/sessions/`:

```bash
uv run horde                                # chat
uv run horde --resume last "and now..."      # continue the most recent session
uv run horde --resume <session-id>           # continue a specific one, as a chat
```

Options:

- `--provider NAME` or `HORDE_PROVIDER=NAME`: which provider (default `groq`, see below)
- `--model NAME` or `HORDE_MODEL=NAME`: which model (default: the provider's, if it has one)
- `--base-url URL`: override the provider's API address
- `--max-steps N`: stop after N model calls (default 10)
- `--max-seconds S`: stop if there's no answer after S seconds
- `--max-tokens N`: stop once N tokens have been used (checked between model calls)
- `--trace-dir DIR`: where to save the trace (default `~/.horde/traces`)

Ctrl+C stops the run at any point (exit code 130).

One line per step is shown on stderr; the final answer goes to stdout.

## Traces

Every run is saved as a JSON Lines trace (one event per line): the task, every
model reply with token usage, every tool call with its approval and result, and
how the run ended.

```bash
horde-trace show   ~/.horde/traces/<file>.jsonl   # readable timeline
horde-trace replay ~/.horde/traces/<file>.jsonl   # rerun with the recorded model replies (no API calls)
```

Replay runs tools for real, behind the usual approval prompt.

## Project instructions

Put an `AGENTS.md` (or `HORDE.md`) in your project. Its contents are added to
the agent's system prompt for every new conversation started there.

## Model providers

| Provider | API format | Key variable | Default model |
|----------|------------|--------------|---------------|
| `groq` | OpenAI | `GROQ_API_KEY` | `openai/gpt-oss-120b` |
| `anthropic` | Anthropic | `ANTHROPIC_API_KEY` | `claude-opus-5-5` |
| `gemini` | Gemini | `GEMINI_API_KEY` | pass `--model` |
| `openai` | OpenAI | `OPENAI_API_KEY` | pass `--model` |
| `openrouter` | OpenAI | `OPENROUTER_API_KEY` | pass `--model` |
| `deepseek` | OpenAI | `DEEPSEEK_API_KEY` | pass `--model` |
| `mistral` | OpenAI | `MISTRAL_API_KEY` | pass `--model` |
| `xai` | OpenAI | `XAI_API_KEY` | pass `--model` |
| `together` | OpenAI | `TOGETHER_API_KEY` | pass `--model` |
| `fireworks` | OpenAI | `FIREWORKS_API_KEY` | pass `--model` |
| `cerebras` | OpenAI | `CEREBRAS_API_KEY` | pass `--model` |
| `ollama` | OpenAI | none (local) | pass `--model` |
| `custom` | OpenAI | `HORDE_API_KEY` (optional) | pass `--model` and `--base-url` |

```bash
horde --provider anthropic "task"
horde --provider gemini --model <gemini-model> "task"
horde --provider custom --base-url http://localhost:8000/v1 --model my-model "task"
```

Model names change often; check the provider's model list. Defaults are only
set where they've been verified.

## Tools

| Tool | Asks before running |
|------|---------------------|
| `calculator` | no |
| `read_file` | only for paths outside the working directory |
| `write_file` | yes |
| `edit_file` | yes |
| `list_files` | only outside the working directory |
| `search_files` | only outside the working directory |
| `update_plan` | no |
| `run_shell` | yes |

The prompt shows the tool and its arguments. Answer `y` (yes), `n` (no) or
`a` (always allow this tool for the rest of this run). Anything else, or no
terminal, means no.

### Adding a tool

```python
from typing import Annotated
from horde.tools import tool

@tool(needs_approval=True)   # or just @tool
def greet(name: Annotated[str, "who to greet"], times: int = 1) -> str:
    """Greet someone."""   # the docstring becomes the description the model sees
    return f"hello {name}\n" * times
```

The JSON Schema is generated from the type hints. Add the tool to
`DEFAULT_TOOLS` in `src/horde/builtin_tools.py`.
