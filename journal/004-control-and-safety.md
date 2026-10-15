# 004 — Feature 3: Control and safety

## Goal

Close the gaps listed in [003](003-tools.md):

| Gap | Fix |
|-----|-----|
| `read_file` could read any file (e.g. `~/.ssh`) without asking and send it to Groq | **Workspace boundary**: outside the working directory needs approval |
| Long tasks would mean many prompts | **"Always" answer**: allow one tool for the rest of the run |
| Ctrl+C printed a Python traceback | **Clean interrupt**: message + exit code 130 |
| `max_steps` doesn't bound wall-clock time | **`--max-seconds`** time limit |

## Context

The first live run ([003, "Live test"](003-tools.md#live-test-first-run-against-groq))
showed a model attempting an unrequested shell command. Safety is a real
requirement, not just a theoretical one.

## Options considered

### What should happen outside the working directory?

| Option | Pros | Cons |
|--------|------|------|
| Always block | Simplest, strongest | The agent can never help with files elsewhere, even when you want it to |
| **Ask** | You stay in control, nothing is impossible | One more prompt |
| Allow-list of directories in a config file | Flexible | Config files are premature for one rule |

**Chosen: ask.** It matches the existing approval model, and the project
owner preferred it.

### How does a tool say "approval depends on the arguments"?

`needs_approval` was `True`/`False`. Now it can also be a **function of the
arguments**: `read_file` uses "is the path outside the workspace?". The loop
calls `tool.requires_approval(arguments)` and doesn't care which kind it is.
If that function crashes (e.g. a missing argument), the answer is "ask":
**fail closed** again.

### How is "inside the workspace" decided?

Comparing strings is wrong: `sub/../../secret.txt` *starts* inside but ends up
outside, and a symlink `link.txt → /etc/passwd` *looks* inside. So we
**resolve the real path first** (`Path.resolve()` follows `..` and symlinks),
then check `is_relative_to(cwd)`. This class of bug is called **path
traversal**, and it's one of the most common security holes in real software.

### Where does "always allow" live?

In the CLI's `TerminalApprover`, not the loop. "Always" is a *user-interface*
decision about how to ask; the loop only needs a yes/no. Because `approve` was
injected in feature 2, this needed **no change to the loop at all**. It's
remembered per tool, for one run only, and never saved to disk.

### Time limit: where is it checked?

Before each model call. That's simple and catches the common case (many slow
steps). It doesn't interrupt a single call in progress; the HTTP client's
60-second timeout and `run_shell`'s timeout cover those.

## What was done

```
src/horde/tools.py          needs_approval can be a function; Tool.requires_approval()
src/horde/builtin_tools.py  is_inside_workspace(); read_file asks outside the workspace
src/horde/loop.py           LimitReached base class, TimeLimitReached, max_seconds
src/horde/cli.py            TerminalApprover (y / n / always), --max-seconds, Ctrl+C -> 130
tests/test_safety.py        new: 11 tests
tests/test_tools.py         approval test updated for the new API
```

### Code walkthrough

- **`is_inside_workspace(path)`**: one line,
  `Path(path).resolve().is_relative_to(Path.cwd().resolve())`. Both sides are
  resolved so a symlinked working directory also works.
- **`Tool.requires_approval(arguments)`**: returns the bool, or calls the
  function inside `try`, falling back to `True`.
- **Exception hierarchy**: `StepLimitReached` and `TimeLimitReached` both
  inherit from `LimitReached`, so the CLI catches *any* limit with one
  `except` and new limits (tokens, cost) can be added later without touching it.
- **`KeyboardInterrupt`**: Ctrl+C raises it anywhere: during a model call,
  inside a shell command, or at the approval prompt. It's a `BaseException`, not
  an `Exception`, so `run_tool`'s `except Exception` deliberately doesn't
  swallow it; it travels up to `main()`, which prints `interrupted` and exits
  with **130** (128 + signal number 2, the Unix convention for Ctrl+C).

## How it was tested

`uv run pytest` gives **30 passed** (19 before + 11 new).

| New test | Proves |
|----------|--------|
| workspace boundary | relative, nested, `..`, absolute paths classified correctly |
| symlink pointing outside counts as outside | symlink escape is caught |
| read_file asks only outside workspace | the per-argument approval decision |
| reading outside is denied without approval | end-to-end through `run_tool`, and allowed when approved |
| approval check that crashes fails closed | broken checks mean "ask" |
| stops at time limit | `max_seconds` with a deliberately slow fake model |
| terminal approver yes and no | `y` allows; `n` and empty deny |
| terminal approver always is per tool | `a` skips later prompts for that tool only |
| terminal approver denies without terminal | `EOFError` means deny |
| Ctrl+C exits cleanly | exit code 130 and the `interrupted` message |
| limit is reported as error | exit code 1 with a readable message |

**Tests use `monkeypatch`** (a pytest fixture) to swap `input()`, the working
directory, `sys.argv` and even `GroqModel` for the duration of one test. That
lets us test the CLI without a terminal or network.

**Live runs** (`openai/gpt-oss-120b`, no terminal attached):
- "read `/home/manish/.bashrc`" triggered the prompt and was denied; the model
  asked the user for permission instead of guessing.
- "read `PLAN.md` and count the roadmap features" ran without a prompt and the
  answer was correct (13).

## Known gaps

- **No OS sandbox.** An approved shell command still runs with your full
  permissions. Needs a container or a sandboxing tool. It deserves its own proposal.
- **No token or cost budget.** That needs usage numbers from each response,
  which comes with feature 4.
- **Noisy log.** The step log prints whole tool results (a full file). Feature 4
  replaces the log with a proper trace.
- **"Always" is per tool, not per command.** "Always allow `run_shell`"
  allows *any* command. Finer rules (e.g. allow only `ls`/`cat`) would be a
  policy system, to add when needed.

## What you should learn here

- **Resolve before you compare.** Paths, URLs and usernames all have many
  spellings for the same thing. Normalise first, then check.
- **Fail closed, everywhere.** No approver, no terminal, a crashing check:
  all of them mean "don't run".
- **Good seams pay off.** "Always allow" needed no loop change, because the
  approval decision was injected in feature 2.
- **Use exception hierarchies for families of errors.** One `except
  LimitReached` handles every current and future limit.
- **Know `Exception` vs `BaseException`.** Catching `Exception` lets Ctrl+C
  through, which is what you want.

## Next

Feature 4: observability, with a structured trace of every step (model calls,
tool calls, approvals, timings, token usage), replacing the noisy log and
enabling token and cost budgets.
