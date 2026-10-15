# 002 — Feature 1: The core agent loop

## Goal

The smallest thing that is really an agent: a model gets a task, can call a
tool, sees the result, and keeps going until it answers.

## Context

- Language: Python 3.12. Provider: Groq ([001](001-language-choice.md)).
- Package and environment manager: **uv**, which is fast and replaces
  `venv` + `pip` + `pip-tools` with one tool.
- No API key yet, so everything must be testable without one.

## The big idea: what an agent loop is

A language model on its own only turns text into text. It can't *do* anything.
The harness gives it hands:

```
          ┌────────────────────────────────────────────┐
          ▼                                            │
  messages ──► model ──► reply has tool_calls? ──yes──► run tools,
                                │                      append results
                                no
                                ▼
                          final answer
```

1. **Think**: send the whole conversation plus the list of tools to the model.
2. **Act**: if the reply asks for tools, the harness runs them. The model never
   runs anything itself; it only *asks*.
3. **Observe**: append each tool result to the conversation.
4. **Repeat** until the model replies without asking for a tool.

Every harness in the [landscape](ref-harness-landscape.md), from Claude Code to
Hermes Agent, has this loop at its heart. Everything else is built around it.

## The message protocol (chat completions format)

The conversation is a list of messages, each with a `role`:

| role | who writes it | example |
|------|---------------|---------|
| `system` | harness | "You are a helpful agent…" |
| `user` | you | "what is 17 * 23 + 5?" |
| `assistant` | model | either text, or `tool_calls: [{id, function: {name, arguments}}]` |
| `tool` | harness | `{tool_call_id: "call_1", content: "396"}` |

Important details:
- `arguments` arrives as a **JSON string**, not an object, so we must
  `json.loads` it, and it can be malformed.
- Each `tool` message must carry the `tool_call_id` it answers, so the model
  can match results to requests when it asks for several tools at once.
- The model is **stateless**. We resend the full conversation on every call.
  That's why long agent runs get expensive, and it's the problem memory and
  context management solve later.

## Options considered

| Question | Options | Choice and why |
|----------|---------|----------------|
| HTTP client | `httpx` directly / `openai` SDK / `groq` SDK | `httpx`: you see the real JSON, nothing hidden |
| Sync or async | sync / `asyncio` | sync: nothing runs in parallel yet |
| Model abstraction | base class / interface / none | none: any object with `complete(messages, tools)` works (**duck typing**). We'll formalise it at feature 5, when a second provider exists |
| First tool | calculator / file read / shell | calculator: harmless; real tools are feature 2 |
| Tool errors | raise / return as text | return as text, so the model can see the mistake and try again |

## What was done

```
pyproject.toml        project metadata, dependency (httpx), `horde` command
src/horde/tools.py    Tool dataclass + safe calculator
src/horde/groq.py     GroqModel.complete(): one HTTP POST
src/horde/loop.py     run_agent(): the loop
src/horde/cli.py      `horde "task"`
tests/test_loop.py    8 tests, fake model, no network
README.md             setup and usage
.gitignore
```

Commands:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh   # install uv
uv sync                                           # create .venv, install deps, write uv.lock
uv run pytest                                     # run tests
```

### Code walkthrough

- **`loop.py`** is the heart, about 40 lines. Read it first.
  - `run_agent` builds the message list, then loops at most `max_steps` times.
  - We copy only `role`, `content` and `tool_calls` from the model's reply
    before appending it, because some models return extra fields that the API
    rejects if they're sent back.
  - `run_tool` turns every failure into an `Error: …` string. An unknown tool,
    bad JSON or an exception inside the tool all go back to the model as text,
    instead of crashing the run.
  - `log` is an optional callback. The CLI prints steps to stderr, so you
    can watch the agent work while stdout stays clean for the answer.
- **`tools.py`**: a `Tool` is a function + name + description + JSON Schema.
  The model only sees the schema. The calculator **never uses `eval()`**: it
  parses the expression with `ast` and allows only numbers and arithmetic
  operators. Text from a model is untrusted input.
- **`groq.py`**: builds the request body, sends it, and on failure raises an
  error *including the response body*. `raise_for_status()` would hide the
  useful part ("model not found", "invalid key"…). The `client` parameter lets
  tests swap in a fake network.
- **`cli.py`**: argparse, wiring, exit code 0/1.

### Project layout notes

- **`src/` layout**: code lives in `src/horde/`, not `horde/`. Tests then run
  against the *installed* package, not whatever happens to be in the current
  directory. This catches packaging mistakes early.
- **`pyproject.toml`** is the modern standard for Python project config.
  `[project.scripts]` creates the `horde` command.
- **`uv.lock`** pins exact versions of every dependency, so everyone gets the
  same environment. Commit it.

## How it was tested

`uv run pytest` gives **8 passed**, with no network and no API key:

| Test | Proves |
|------|--------|
| returns answer when no tool is called | the loop ends correctly |
| runs tool and feeds result back | the full think → act → observe cycle, and the `tool_call_id` |
| unknown tool is reported to model | the model's mistakes don't crash the harness |
| tool error is reported to model | exceptions inside tools become text |
| stops at step limit | the agent can't loop forever |
| calculator does arithmetic only | the code-injection attempt is rejected |
| groq request shape | correct URL, auth header and body, using `httpx.MockTransport` |
| groq error includes response body | useful error messages |

**The fake model** is the key testing technique for agents: a scripted object
that returns pre-written replies and records what it was sent. Tests become
fast, free and deterministic, which a real model never is.

Also checked by hand: `horde "hi"` without a key prints
`error: GROQ_API_KEY is not set` and exits with code 1.

**Not yet tested:** a live run against Groq, which needs a key. The default
model `llama-3.3-70b-versatile` could not be confirmed against Groq's current
model list. If it's gone, use `--model` with a tool-capable model from
console.groq.com.

## What you should learn here

- **An agent is a loop, not a model.** The model decides; the harness acts.
- **The model only asks; the harness decides whether to act.** That separation
  is where all future safety controls go (feature 3).
- **Errors are information.** Feeding them back lets the model correct
  itself. This is the seed of feature 7.
- **Always have a stop condition.** `max_steps` is the simplest guard.
- **Treat model output as untrusted input.** No `eval`, ever.
- **Fake the model in tests.** Test the harness logic deterministically, and
  test real models separately.
- **Duck typing before abstraction.** One `complete()` method is the whole
  interface until a second provider proves what it needs to be.

## Next

Feature 2: a tool interface that makes adding tools trivial, plus real tools
(read/write files, run shell commands).
