# 006 — Feature 5: All major model providers

## Goal

Make "run any model" real: support the major providers, and find out what the
model interface needs to be now that there's more than one.

## Context

- The roadmap said "a second provider". The project owner widened it: **support
  all major providers**.
- Only a Groq key is available. Everything else is tested against recorded
  fake responses, and verified live only once keys exist.
- Model names expire. In [003](003-tools.md) the default Groq model had been
  retired.

## The big idea: providers vs API formats

"All major providers" sounds like a dozen integrations. It's actually **three
API formats**:

| Format | Providers |
|--------|-----------|
| **OpenAI chat completions** | OpenAI, Groq, OpenRouter, DeepSeek, Mistral, xAI, Together, Fireworks, Cerebras, Ollama, any custom server |
| **Anthropic Messages** | Anthropic (Claude) |
| **Google Gemini** | Gemini |

So we wrote **3 adapters**, and each provider is a line of configuration: which
format, which address, which environment variable holds the key.

```
                    ┌── OpenAICompatibleModel ── groq, openai, openrouter, deepseek, …
loop ── Model ──────┼── AnthropicModel ───────── anthropic
 (OpenAI format)    └── GeminiModel ──────────── gemini
```

## Options considered

### What is the internal message format?

| Option | Pros | Cons |
|--------|------|------|
| Design our own neutral format | "Clean" | Every adapter translates, including the one most providers use; a new format to learn and document |
| **Keep OpenAI's format internally** | Already used by the loop, traces and tests; most providers speak it natively; translation only where needed | Anthropic and Gemini adapters must translate both ways |

**Chosen: OpenAI's format.** It is the de facto standard. Inventing our own would
be speculative abstraction.

### Provider-specific data that must survive the round trip

This was the surprise of the feature. Modern reasoning models return data that
must be sent back **unchanged** on the next request:
- **Claude** returns `thinking` blocks, which must be echoed back on the same model.
- **Gemini** attaches a `thoughtSignature` to function-call parts. Gemini 3
  *rejects* a request where a signature is missing.

Our internal format has nowhere for these. Options:

| Option | Problem |
|--------|---------|
| Drop them | Requests fail (Gemini) or reasoning is lost (Claude) |
| Add `thinking`, `signature`, … fields to our format | Our format fills up with every provider's quirks |
| **One opaque `provider_state` field** | Each adapter stores its raw reply there and reuses it verbatim; the loop just carries it; other adapters strip or ignore it |

**Chosen: `provider_state`.** The loop learned exactly one new thing: keep that
field. This is the classic **opaque handle** pattern: the loop holds the data
without knowing what it is.

### Default models

A web search for current model IDs returned contradicting sources. So:
- **Defaults only where verified**: Groq `openai/gpt-oss-120b` (worked live),
  Anthropic `claude-opus-5-5` (from Anthropic's own reference).
- **Every other provider needs `--model`** (or `HORDE_MODEL`), with a clear
  error. A guessed default that fails with "model not found" is worse than an
  honest "please choose".

### Making the contract explicit

Since feature 1 the model contract was duck-typed. With three real
implementations we now know its exact shape, so it's written down as a
`typing.Protocol` (`horde.models.base.Model`). A Protocol describes the
required methods without forcing classes to inherit from anything. Type
checkers can verify it, and `FakeModel` still works without changes.

## What was done

```
src/horde/models/__init__.py       Provider settings, PROVIDERS (13 entries), create_model()
src/horde/models/base.py           Model protocol, shared HTTP call + error message
src/horde/models/openai_compat.py  OpenAI-format adapter (strips provider_state)
src/horde/models/anthropic.py      Anthropic adapter (both directions)
src/horde/models/gemini.py         Gemini adapter (both directions)
src/horde/groq.py                  removed (now the "groq" preset)
src/horde/loop.py                  keeps provider_state; run_start records the model name
src/horde/cli.py                   --provider, --base-url; setup errors before creating a trace
src/horde/trace.py                 shows the model in the timeline
tests/test_models.py               new: 16 tests (replace the 2 old Groq tests)
```

### Code walkthrough

- **`create_model(provider, model, base_url)`** checks the provider exists,
  then picks the model (`--model`, then `$HORDE_MODEL`, then the default). It
  checks there's an address and a key (unless optional, as for Ollama), then
  builds the right adapter. Every failure is a one-line error saying what to do.
- **All adapters share one constructor** `(name, model, base_url, api_key, client)`
  and one method, `complete()`. The registry can treat them interchangeably.
- **Anthropic translation** (`to_anthropic` / `from_anthropic`):
  - `system` messages become the top-level `system` field.
  - An assistant message with `tool_calls` becomes `text` + `tool_use` blocks;
    arguments go from a JSON *string* to a JSON *object* (`input`).
  - `tool` messages become `tool_result` blocks in a **user** message, and
    consecutive results are merged into **one** message, which Anthropic
    expects for parallel tool calls.
  - Usage: `input_tokens` + cache tokens = prompt; `output_tokens` = completion.
  - `stop_reason: "refusal"` becomes a clear error.
  - **Refusal fallbacks** are enabled for current Claude models: if the model
    declines, the API reruns the request on a fallback model inside the same call.
- **Gemini translation** (`to_gemini` / `from_gemini`):
  - Roles become `user` / `model`; content becomes `parts`.
  - Tool results are matched by function **name**, so the adapter remembers
    which call id belonged to which name.
  - Gemini doesn't always give calls an id, so we invent one prefixed
    `horde_` and never send invented ids back to Gemini.
  - Parts marked `thought: true` are reasoning, not the answer, so they're
    excluded from the text.
  - Tools without arguments omit `parameters`, because Gemini rejects an empty object schema.
- **Timeouts** went from 60 s to 600 s: reasoning models can think for
  minutes before answering.

## How it was tested

`uv run pytest` gives **61 passed** (45 before, minus 2 old Groq tests, plus 18 new).

**`FakeServer`** uses `httpx.MockTransport`, so each adapter talks to a fake
network that records every request and returns canned JSON. We check the
exact URL, headers and body sent, and the exact message we get back, with no
keys and no network.

| Area | Tests prove |
|------|-------------|
| `create_model` | defaults, env override, unknown provider, missing model, missing base URL, missing key, Ollama without key |
| OpenAI-compatible | URL, auth header, `provider_state` stripped, no auth header without a key, error body included |
| Anthropic | request shape (system, tools, tool_use, tool_result), fallbacks only on supported models, reply translation and usage, **own blocks (incl. thinking) sent back unchanged**, parallel results in one message, refusal |
| Gemini | URL, header, systemInstruction, declarations (no empty schema), reply translation (thought parts excluded), **own parts (incl. thoughtSignature) sent back unchanged**, invented ids not sent, empty/blocked reply |
| Loop | `provider_state` is kept and sent back |
| CLI | a setup error creates no trace file |

**Live runs:**
- `--provider groq` (default): the PLAN.md task answered **91** in 3 steps.
  The timeline now shows `[groq:openai/gpt-oss-120b]`.
- `--provider custom --base-url https://api.groq.com/openai/v1 --model openai/gpt-oss-20b`
  reached the same server through the *generic* path, and answered 144.
- `--provider anthropic` without a key gave `error: ANTHROPIC_API_KEY is not set`.
- `--provider openai` without a model gave `error: provider 'openai' has no
  default model: pass --model or set HORDE_MODEL`.

**Not verified live:** Anthropic, Gemini, and every OpenAI-compatible provider
other than Groq (no keys). The translation logic is tested against the
documented formats, but real APIs can differ in details. The first live run on
each provider should be watched.

## Known gaps

- **No streaming.** Replies arrive all at once; a long answer means waiting.
- **No retries.** A rate limit (HTTP 429) or a temporary server error ends the run.
- **Model names aren't discoverable** from the harness. A `--list-models`
  command would help (most providers have a `/models` endpoint).
- **Cloud-hosted variants** (AWS Bedrock, Google Vertex AI, Azure) need
  cloud-specific authentication and aren't supported.
- **Anthropic: API key only.** Other credential sources (e.g. `ant auth login`
  profiles) aren't read.
- **Switching provider mid-conversation** isn't supported. `provider_state` from
  one provider is ignored by another, which would lose its reasoning.

## What you should learn here

- **Count formats, not vendors.** A dozen providers collapsed into three adapters
  plus a table of settings.
- **Translate at the edges.** One internal format everywhere; conversion only
  where data enters or leaves.
- **Opaque handles for data you don't understand.** `provider_state` lets each
  adapter carry what it needs without the core learning every provider's quirks.
- **Abstract when you have real cases.** The `Model` Protocol was written after
  three implementations existed, so it describes reality, not a guess.
- **Don't guess facts that expire.** No default model is better than a wrong one;
  make the error say exactly what to do.
- **Fake the network, not the code.** `MockTransport` tests the real adapter
  code, including JSON encoding, headers and URLs.

## Next

Feature 6: session persistence, saving a conversation and resuming it later.
