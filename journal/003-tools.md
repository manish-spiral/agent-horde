# 003 — Feature 2: Tool interface and real tools

## Goal

1. Make adding a tool trivial: write a normal Python function, add `@tool`.
2. Give the agent real abilities: read files, write files, run shell commands.
3. Because those touch your machine, **ask the user before anything with side
   effects runs**.

## Context

- In feature 1, a tool needed a hand-written JSON Schema. That's fine for one
  tool, but tedious and error-prone for many.
- Writing files and running shell commands can damage things. The plan had
  safety as feature 3, but shipping a shell tool with no guard at all would break
  the principle "safe by default". So a minimal approval step comes now;
  feature 3 makes it richer (policies, limits, interrupt).

## Options considered

### How to describe a tool's arguments

| Option | Pros | Cons |
|--------|------|------|
| Hand-written JSON Schema (feature 1) | Explicit, any shape | Repetitive; schema and function drift apart |
| Pydantic models | Rich validation, nested types | A new dependency and concept to learn |
| **Read the function signature** (`inspect` + type hints) | The function *is* the spec; no extra deps | Only simple types for now |

**Chosen: the function signature.** Type hints give the JSON types, a default
value means "optional", the docstring becomes the description, and
`Annotated[str, "…"]` adds a per-argument description. If tools ever need lists
or nested objects, we'll extend `_JSON_TYPES` or switch to Pydantic, when a
real tool needs it.

### Where the approval check lives

| Option | Problem |
|--------|---------|
| Inside each tool | Every tool author must remember it; easy to forget |
| In the CLI | Other front-ends (web UI, sub-agents) would skip it |
| **In the loop's `run_tool`, driven by a flag on the tool** | One place, can't be bypassed, any front-end plugs in its own way of asking |

The loop doesn't know *how* to ask; it calls an `approve(name, arguments)`
function it was given. The CLI passes one that prompts in the terminal. Tests
pass one that returns True or False. A future web UI would pass one that shows
a button. This is **dependency injection**: pass in the behavior instead of
hard-coding it.

### Default when no approver is given

**Deny.** If someone calls `run_agent` and forgets to pass `approve`, risky
tools refuse to run instead of silently running. This is called **fail closed**.
Same in the CLI: no terminal to ask (e.g. piped input) means "no".

## What was done

```
src/horde/tools.py          Tool + @tool decorator (schema from signature)
src/horde/builtin_tools.py  calculator (moved here), read_file, write_file, run_shell
src/horde/loop.py           approval check, JSON validation, output truncation
src/horde/cli.py            terminal approval prompt, all built-in tools enabled
tests/test_tools.py         new: decorator + each tool
tests/test_loop.py          new: approval, bad JSON, truncation
```

### Code walkthrough

- **`tools.py`: `@tool`**
  - `inspect.signature` lists the parameters and their defaults.
  - `get_type_hints(..., include_extras=True)` reads the type hints and keeps
    the `Annotated` descriptions.
  - Unsupported types raise `TypeError` *when the module is imported*, so a
    broken tool fails immediately instead of confusing the model at runtime.
  - `tool` works both bare (`@tool`) and with options
    (`@tool(needs_approval=True)`). That's why it returns either a `Tool` or a
    wrapper, a common Python decorator pattern.
- **`builtin_tools.py`**
  - `read_file`: no approval, since reading has no side effects (but see "Known
    gaps").
  - `write_file`: approval; creates parent directories.
  - `run_shell`: approval; `timeout` so a hanging command can't freeze the
    agent; `stdin=DEVNULL` so a command waiting for input fails instead of
    hanging; returns the exit code, stdout and stderr so the model can tell
    success from failure.
  - `DEFAULT_TOOLS` is the list the CLI hands to the agent.
- **`loop.py`: `run_tool`** now runs in clear stages, each failure returning
  text to the model:
  1. Unknown tool?
  2. Arguments valid JSON? Is it an object?
  3. Needs approval, and was it denied?
  4. Run it; exceptions become `Error: …`.
  5. Result longer than 20,000 characters? Truncate it, and *say so*, so the
     model knows it didn't see everything.
- **`cli.py`: `ask_user`** prints the tool and its arguments (long values
  cut to 1,000 characters) to **stderr** and reads y/N. Only `y`/`yes` allows.

## How it was tested

`uv run pytest` gives **19 passed** (8 before + 11 new).

| New test | Proves |
|----------|--------|
| decorator builds schema from function | types, required vs optional, descriptions, docstring |
| decorator rejects unsupported types | broken tools fail loudly and early |
| only side-effect tools need approval | the right tools are gated |
| write then read file | round trip, parent directories created |
| read missing file raises | the loop turns this into `Error: FileNotFoundError…` |
| run_shell reports exit code and output | stdout, stderr and exit code all reach the model |
| run_shell times out | a hanging command can't freeze the agent |
| denied by default | fail closed |
| approver sees parsed arguments and can allow | the approver gets real data to decide on |
| invalid JSON arguments are reported | malformed model output doesn't crash |
| long results are truncated | context protection, with a visible marker |

Manual check of the terminal prompt: `y` gives allowed; `n`, empty input or
no terminal gives denied.

Still not tested live against Groq (no key yet).

## Live test (first run against Groq)

Task: `horde "what is 17 * 23 + 5? use the calculator"`, run with no
terminal attached, so every approval request is answered "no".

1. **The default model had been retired.** Groq answered
   `404 … model llama-3.3-70b-versatile does not exist`. Because `groq.py`
   includes the response body in its errors, the cause was obvious at once.
   Listing the models (`GET /openai/v1/models`) showed the tool-capable chat
   models available: `openai/gpt-oss-120b`, `openai/gpt-oss-20b`,
   `qwen/qwen3.8-27b`. The default is now `openai/gpt-oss-120b`.
2. **`openai/gpt-oss-120b`**: `calculator("17 * 23 + 5") -> 396`, then the
   final answer. 2 steps, exactly as intended.
3. **`qwen/qwen3.8-27b`**: its *first* action was a `run_shell` call nobody
   asked for, trying to write files into `.gsd-global/rules/` and
   `.gsd-local/`. The approval check denied it, the model received
   `Error: the user did not allow run_shell to run`, then used the
   calculator and answered 396 correctly. No files were created.

Lessons from the live run:
- **Models do unexpected things, even on trivial tasks.** The approval gate
  isn't theoretical; it stopped a real unrequested side effect on the very
  first live run.
- **Fake-model tests prove the harness logic; only live runs reveal model
  behavior.** You need both.
- **Model names expire.** Keep the default in one place and overridable
  (`--model`, `HORDE_MODEL`).
- **Good error messages pay off immediately.**

## Known gaps (on purpose, for feature 3)

- **`read_file` can read any file** your user can, e.g. `~/.ssh/id_rsa`, and
  what it reads **is sent to Groq**. Reading needs no approval today.
- **No sandbox.** Approved shell commands run with your full permissions.
- **No "always allow"**, so long tasks mean many prompts.
- **No interrupt or cost limit** beyond `max_steps`.

## What you should learn here

- **Let the code be the spec.** Generating schemas from type hints keeps the
  description and the implementation in sync automatically.
- **Put safety checks at the choke point.** Every tool call goes through
  `run_tool`, so that's where the guard goes, not in each tool.
- **Inject decisions, don't hard-code them.** `approve` is a function
  parameter, so the same loop works in a terminal, a test, or a future UI.
- **Fail closed.** When in doubt (no approver, no terminal), deny.
- **Protect the context window.** Everything a tool returns is resent on
  every step; cap it and say when you did.
- **Fail early.** Bad tool definitions error at import, not mid-task.

## Next

Feature 3: control and safety, including path restrictions for file tools,
allow-lists / "always allow", cost and time limits, and interrupting a run.
