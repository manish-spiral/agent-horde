# 010 — Feature 9: Automatic retries for temporary API failures

## Goal

Don't end a run because of a rate limit or a momentary server error. These are
common on free tiers (Groq) and with busy providers.

## Options considered

| Question | Choice and why |
|----------|----------------|
| Where? | In `post_json`, the one HTTP call every adapter shares, so all 13 providers get it at once. |
| What is retried? | Statuses that are usually temporary: 408, 409, 429 (rate limit), 500, 502, 503, 504, 529 (overloaded), plus connection errors. **Not** 400/401/404: those won't fix themselves, so retrying just wastes time. |
| How long to wait? | The server's `retry-after` header if present (capped at 30 s), else **exponential backoff**: 1, 2, 4 s. |
| How many times? | 3 retries (4 attempts), then the usual clear error. |

## What was done

```
src/horde/models/base.py   post_json retries; _wait_seconds()
tests/test_retries.py      new: 5 tests
```

A first draft used `"response" in locals()` to tell a failed connection from a
bad status. It was replaced before committing, because after a connection
error it could have reused a stale response from the previous attempt. Each
attempt now starts with `response = None`.

## How it was tested

`uv run pytest` gives **81 passed** (76 + 5 new). `time.sleep` is replaced by a list
that records the waits, so tests run instantly and can assert the exact backoff:
429 then 503 then success (waits 1, 2), `retry-after: 7` honoured, connection
error retried, giving up after 3 retries with the server's message, and 400
never retried.

Live: `horde "what is 6*7?"` on Groq still answers 42.

## What you should learn here

- **Retry only what can succeed later.** Classify errors as temporary
  (rate limits, 5xx, network) or permanent (bad request, auth).
- **Back off exponentially and respect `retry-after`.** Hammering a
  rate-limited server makes things worse.
- **Make time injectable in tests.** Faking `sleep` keeps tests fast and lets
  you check the waiting logic exactly.
