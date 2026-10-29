# 019 — Feature 18: Feedback when you deny a tool

## Goal

A bare "no" leaves the model guessing why. Let the user say **what to do
instead** at the approval prompt, and pass that straight to the model. This is
the first, most direct piece of "learning from feedback".

## Decisions

| Question | Choice and why |
|----------|----------------|
| How do you give feedback? | At the prompt, type anything other than y / n / a (e.g. "No, use list_files instead"). No extra prompt; `n` or Enter is still a plain no. |
| How does it reach the model? | An approver may now return **a string**: denied, plus feedback. The tool result becomes `Error: the user did not allow run_shell to run. They said: No, use list_files instead`. |
| Compatibility | Approvers returning `True`/`False` work unchanged. Only exactly `True` allows, so a stray truthy value can never approve by accident (fail closed). |
| Trace | A string decision is recorded as `denied`; the feedback is in the tool result. |

## What was done

```
src/horde/loop.py   Approver may return bool | str; feedback added to the denial result
src/horde/cli.py    typed text at the prompt is returned as feedback
tests/test_safety.py  new: 1 test
```

## How it was tested

`uv run pytest` gives **114 passed** (113 + 1 new): typed text comes back from the
approver, and `run_tool` turns it into the denial message the model sees.
Existing yes/no/always/no-terminal tests still pass unchanged.

## Next steps toward "learning"

Feedback here affects the current run. To make it *stick*, the agent can
`remember` it ([013](013-long-term-memory.md)) or `save_skill`
([017](017-skills.md)); both already exist and ask for approval.

## What you should learn here

- **A refusal with a reason is far more useful than a refusal.**
- **Check for `is True`, not truthiness, when a value means "allow".**
