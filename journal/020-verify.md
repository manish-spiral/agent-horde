# 020 — Feature 19: Self-correction with `--verify`

## Goal

Agents often *say* they're done when they aren't. Let a real check decide:
`horde --verify "uv run pytest -q" "fix the failing test"`.

## How it works

1. The agent works on the task and answers.
2. The harness runs your check command.
3. If it **fails**, the end of its output (last 5,000 characters) goes back to
   the agent as a new message: "The check `…` failed after your last answer: … Fix
   the problem." The same conversation continues.
4. Up to **3** retries. If it still fails, the run ends with exit code 1 and a
   clear error.

## Decisions

| Question | Choice and why |
|----------|----------------|
| Who runs the check? | The **harness**, not the model. The model can't skip it or misreport it. |
| Approval for the check? | None: you wrote the command yourself on the command line. |
| What does the model see? | The exit code and the end of the output, where test failures usually are. |
| Where? | In the CLI around `run_agent`. The loop is unchanged; "check, then continue the conversation" is the same mechanism as chat ([008](008-chat-and-sessions.md)). |

## What was done

```
src/horde/cli.py      --verify, run_check(), retry around run_agent
tests/test_verify.py  new: 3 tests
```

## How it was tested

`uv run pytest` gives **117 passed** (114 + 3 new): a check that fails until the
(fake) agent "fixes" things gets the failure output to the model and then passes;
a passing check needs no retry; a check that never passes stops after 3 retries
with exit code 1.

## What you should learn here

- **Trust checks, not claims.** Running the tests is the best self-correction
  signal a coding agent can get.
- **Feedback loops reuse conversation.** A failed check is just another user
  message.
