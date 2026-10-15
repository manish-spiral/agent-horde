# 005 — Feature 4: Observability

## Goal

Every run leaves a complete, structured record of what happened and why, so
you can see what the agent did after the fact, set a token budget, and rerun a
recorded session without calling the model.

## Context

- The old `log` callback printed text lines, which were hard to read (whole
  files dumped to the terminal) and impossible to analyse afterwards.
- [004](004-control-and-safety.md) left "token and cost budget" open because we
  weren't collecting token usage.
- Trace location: the project owner approved the plan without choosing, so we
  used the recommended `~/.horde/traces/` (overridable with `--trace-dir`).

## The big idea: events, not log lines

The loop no longer *prints* anything. It **emits events**, plain dicts with a
`type`, and whoever ran it decides what to do with them:

```
                   ┌──► TraceWriter   → ~/.horde/traces/<time>.jsonl  (everything)
run_agent ─event─► │
                   └──► print_event   → terminal                     (one short line)
```

That separates **recording** from **displaying**. A future web UI, a metrics
dashboard or a test just passes a different `on_event`. It's the same
dependency-injection idea as `approve` in [003](003-tools.md).

### The four event types

| type | when | key fields |
|------|------|------------|
| `run_start` | once, first | `task`, `tools`, `limits` |
| `model_call` | after each model reply | `step`, `duration`, `usage`, `message` (the full reply) |
| `tool_call` | after each tool runs | `step`, `name`, `arguments`, `approval` (`not_needed`/`approved`/`denied`), `result`, `duration` |
| `run_end` | once, last, **always** | `outcome` (`answer`, `step_limit`, `time_limit`, `token_limit`, `interrupted`, `error`), `answer` or `error`, `steps`, total `usage` |

Every event also has `elapsed` (seconds since the run began), and the trace
writer adds a wall-clock `time`.

## Options considered

| Question | Options | Choice and why |
|----------|---------|----------------|
| Trace format | one JSON document / SQLite / **JSON Lines** | JSONL: append-only, so a crash keeps everything before it; readable with any text tool (`grep`, `jq`, `tail -f`) |
| How does the loop report approval decisions? | change `run_tool` to return them / emit from inside `run_tool` / **wrap `approve`** | Wrapping keeps `run_tool` unchanged: `_run_recorded` passes in an approver that remembers what it answered |
| How to guarantee `run_end`? | emit in every exit path / **`try … except BaseException` → emit → re-raise** | One place catches limits, errors *and* Ctrl+C, records them, then lets them continue up |
| How does a model report tokens? | attribute like `model.last_usage` / **return `(message, usage)`** | Explicit return values are easier to follow and test than hidden state |
| Replay: re-run tools or use recorded results? | recorded results only / **real tools behind the approval prompt** | Real tools let you test *harness* changes against recorded *model* behavior; the prompt keeps it safe |
| Where does trace-reading code live? | in `horde` / **separate `horde-trace` command** | `horde "trace this"` would be ambiguous as a task |

## What was done

```
src/horde/groq.py       complete() returns (message, usage)
src/horde/loop.py       on_event replaces log; 4 event types; token budget; run_end always
src/horde/trace.py      new: TraceWriter, read_trace, ReplayModel, format_event, print_event
src/horde/trace_cli.py  new: `horde-trace show|replay FILE`
src/horde/cli.py        writes a trace, prints short lines, --max-tokens, --trace-dir
pyproject.toml          new command: horde-trace
tests/conftest.py       new: tests never write to the real ~/.horde
tests/test_trace.py     new: 15 tests
tests/test_loop.py, tests/test_safety.py   fake models return (message, usage)
```

### Code walkthrough

- **`loop.py`**
  - `emit(type, **fields)` adds `type` and `elapsed`, then calls `on_event`.
  - `usage` is a `collections.Counter`, which adds dicts key by key, so
    summing token counts across calls is one `update()`.
  - The token check runs **before** each model call, like the time check.
  - `model_calls` counts replies actually received. (The first live run
    reported "3 steps" after only 2 model calls, because it used the loop
    counter, which had already moved on. That bug was caught live and fixed, with a test.)
  - The `except BaseException` block finds the outcome from the exception's
    `outcome` class attribute (each `LimitReached` subclass defines one), emits
    `run_end`, then uses a bare `raise` to re-raise the *same* exception.
- **`trace.py`**
  - `TraceWriter` is a class with `__call__`, so an instance *is* an
    `on_event` function but can also keep the open file and its path.
  - `flush()` after every line, so a crash or Ctrl+C doesn't lose buffered events.
  - The directory is created with mode `0o700` (only you can read it), because
    traces contain file contents and command output.
  - `ReplayModel` is the same idea as the tests' `FakeModel`, but its script
    comes from a real trace.
- **`trace_cli.py`**: `show` prints the timeline plus the answer; `replay` reruns
  with the recorded task and limits (not `max_seconds`, since replay has no
  network delay).

## How it was tested

`uv run pytest` gives **45 passed** (30 before + 15 new).

| New test | Proves |
|----------|--------|
| events describe the whole run | order of events, their contents, token totals |
| approval decision is recorded (×2) | `approved` and `denied` both land in the trace |
| run_end emitted when a limit stops the run | outcome `step_limit`, correct step count |
| run_end emitted on interrupt | Ctrl+C is recorded as `interrupted` |
| token budget stops the run | stops *before* the next model call; steps = calls made |
| final answer kept even if it crosses the budget | a finished answer is never thrown away |
| trace writer writes one JSON object per line | valid JSONL, `time` added |
| trace directory is private | mode 700 |
| CLI saves a trace | end to end through `horde` |
| shorten / format_event | terminal lines |
| replay reproduces a recorded run | same tool calls and results, same answer |
| replay model runs out of replies | clear error |
| horde-trace show and replay | both subcommands end to end |

**`conftest.py`**: pytest loads this file automatically. Its `autouse` fixture
runs for *every* test and points the trace directory at a temporary folder,
so no test can litter your home directory. Verified: after the suite, `~/.horde`
didn't exist.

**Live runs** (`openai/gpt-oss-120b`):
1. "Read PLAN.md, count the roadmap features, multiply by 7" gave `read_file`, then
   `calculator("13 * 7")`, then **91**: 3 steps, 2787 tokens, 2.1 s. The terminal
   showed one short line per step; the trace had 7 events.
2. `horde-trace show` on that trace printed the same timeline.
3. `horde-trace replay` with **`GROQ_API_KEY` unset** produced the same
   steps and answer in 0.0 s, proving no API call was made.
4. `--max-tokens 500` stopped the run as `token_limit` after 2 calls. It had
   actually used **1590** tokens. See "Known gaps".

## Known gaps

- **The token budget is soft.** It's checked between calls, so one call can blow
  past it (500 budget, 1590 used). A hard limit would need to estimate a
  request's size *before* sending it.
- **No cost in money.** Tokens only; prices differ per model and change.
- **Replay can diverge.** Tools rerun for real; if a file changed, the
  recorded model replies may no longer make sense.
- **Traces are never deleted.** There's no cleanup yet.

## What you should learn here

- **Emit events, don't print.** Separate *what happened* from *how it's
  shown*, and every consumer (terminal, file, UI, tests) gets the same data.
- **Structured beats text.** A JSON event can be filtered, summed and
  replayed; a log line can only be read.
- **Make the last event unmissable.** `try/except BaseException` → record →
  re-raise guarantees a `run_end` however the run dies.
- **Record enough to replay.** Storing the model's full replies turns any live
  run into a free, repeatable test, which is very valuable with non-deterministic models.
- **Live runs find bugs unit tests miss.** The wrong step count was only
  noticed by reading real output.
- **Protect tests from the real environment.** `autouse` fixtures in
  `conftest.py` stop tests from touching your real files.

## Next

Feature 5: a second model provider, which will show what the model interface
really needs to be.
