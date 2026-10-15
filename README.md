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
