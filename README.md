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

Options:

- `--model NAME` or `HORDE_MODEL=NAME`: which Groq model to use
- `--max-steps N`: stop after N model calls (default 10)

Steps are logged to stderr; the final answer goes to stdout.

## Tools

| Tool | Asks before running |
|------|---------------------|
| `calculator` | no |
| `read_file` | no |
| `write_file` | yes |
| `run_shell` | yes |

Tools that change things show you their arguments and wait for `y`.
Anything else, or no terminal, means no.

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
