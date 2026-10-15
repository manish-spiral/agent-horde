# 001 — Choosing a language and model provider

## Goal

Pick the language the **core** of the harness is written in, and the first
model provider it talks to.

## Context

- The harness must be open to **any language**. That is a requirement on its
  *boundaries*, not on its core: tools and extensions will talk to the core over
  plain protocols (JSON over stdin/stdout, HTTP, MCP). A tool written in Rust,
  Python or Bash can then plug into a core written in anything.
- The first provider is **Groq** (it has a free tier and is very fast).
- The project owner wants to learn, so readability matters.

## What an agent harness actually does all day

This shapes the language choice more than anything else:

1. Send an HTTP request to a model and **wait** (seconds).
2. Parse JSON (tool calls).
3. Run a tool: a file read, a subprocess, another HTTP call, and **wait** again.
4. Stream text to a terminal or UI.
5. Repeat.

It is **I/O-bound and JSON-heavy**, not CPU-bound. Raw speed almost never
matters; good async I/O, JSON handling, ecosystem and ease of distribution do.

## Options considered

| | TypeScript (Node/Bun) | Python | Go | Rust |
|---|---|---|---|---|
| Async I/O | Built in from day one (event loop) | Good (`asyncio`), added later, two worlds (sync/async) | Excellent (goroutines) | Excellent, but complex |
| JSON | Native — JSON *is* JS objects | Easy (dicts) | Verbose (structs/tags) | Verbose (serde), strict |
| Types for tool schemas | Strong (TS + Zod → JSON Schema) | Optional (type hints + Pydantic) | Static, simple | Very strong |
| LLM SDKs | First-class | First-class (most AI research lands here first) | Fewer, often community | Fewer, often community |
| MCP SDK | Official, reference implementation | Official | Official | Official |
| Distribute a CLI | `npm i -g` / single binary with Bun | Painful (venvs, versions) | Single static binary | Single static binary |
| Terminal/web UI | Huge (Ink, React, VS Code extensions) | OK (Textual, Rich) | Good (Bubble Tea) | Good (Ratatui) |
| Learning curve | Moderate | Easiest | Easy | Hardest |
| Iteration speed | Fast | Fastest | Medium | Slow |

### Real harnesses and their languages

- **TypeScript:** Claude Code, Gemini CLI, Vercel AI SDK, many MCP servers
- **Python:** Aider, OpenHands, SWE-agent, LangChain/LangGraph, smolagents
- **Rust:** OpenAI Codex CLI (rewritten from TypeScript), Goose
- **Go:** Crush

### Why so many harnesses are TypeScript

1. **The work is async I/O.** JavaScript was built around an event loop for
   exactly this: waiting on many network calls without threads.
2. **JSON is native.** Model APIs and tool calls are JSON; in TS there's no
   conversion layer.
3. **Typed tool schemas.** One Zod schema gives you runtime validation, TS
   types *and* the JSON Schema the model needs.
4. **Distribution.** Developers already have Node; `npm install -g` just works.
   Python CLIs often break on environment and version issues.
5. **UI reuse.** The same code can power a terminal UI, a web app and an IDE
   extension, because VS Code and the browser both run JS.
6. **Ecosystem gravity.** MCP's reference SDK and many AI SDKs ship TS first,
   so people follow.

### Why Python is still common

Research and ML live in Python. Harnesses built by researchers, for example
for benchmarking agents, use Python because their surrounding tools are there.

### Why Rust and Go show up

They're used when the harness must ship as one fast binary with tight
sandboxing. That's usually a *later* optimization (Codex started in TS).

### What you give up by choosing something other than TypeScript

**Python**: you lose
- **Easy distribution.** Users need the right Python version and a virtual
  environment. `uv` and `pipx` help, but it's still the most common source of
  "doesn't work on my machine".
- **UI reuse.** No sharing code with a web UI or a VS Code extension, which
  both run JavaScript.
- **Enforced types.** Type hints are optional and not checked at runtime;
  you need Pydantic plus a type checker (mypy/pyright) to get close.
- **One async world.** Sync and async libraries mix badly. One blocking call
  inside the async loop freezes everything, an easy mistake in an agent
  that runs many tools.

You gain: the easiest syntax, the AI/ML ecosystem (embeddings, local models,
notebooks), and the largest number of agent tutorials and examples.

**Go**: you lose
- **Comfortable dynamic JSON.** Tool-call arguments are arbitrary JSON;
  in Go you either define a struct for everything or juggle `map[string]any`.
- **Union types.** A model message is "text OR tool call OR image". TS expresses
  that in one line; Go needs interfaces and type switches.
- **AI ecosystem breadth.** Major providers now have Go SDKs, but fewer
  examples, integrations and community libraries exist.
- **UI reuse.** Same as Python.

You gain: one static binary, very simple concurrency (goroutines suit
sub-agents running in parallel), fast startup, a small and simple language.

**Rust**: you lose
- **Iteration speed.** Compile times and the borrow checker make every
  feature slower to write, especially while learning.
- **Learning focus.** You'd be learning Rust *and* agent design at once.
- **Comfortable dynamic JSON.** `serde` is excellent but strict; loose,
  model-generated JSON needs more ceremony.
- **AI SDKs.** Mostly community-maintained.
- **UI reuse.** Same as Python.

You gain: top performance, memory safety, strong OS-level sandboxing, one
binary, and very reliable long-running processes.

**What you give up by choosing TypeScript:**
- It's not the easiest to learn. TS's type system gets deep.
- It needs Node or Bun installed, unless you compile a binary with Bun.
- No ML ecosystem. That's fine here, because the models run remotely.
- npm dependency churn and supply-chain risk, so keep dependencies few.

### The honest bottom line

| Choosing… | Biggest real loss for *this* project |
|-----------|--------------------------------------|
| Python | Distribution and UI reuse |
| Go | Expressiveness for dynamic JSON and message types |
| Rust | Speed of learning and building |
| TypeScript | Not the simplest language to learn |

And because tools and extensions plug in over protocols, the core's language
is **not a lock-in** for anything that connects to it.

## Model provider: Groq

- Groq serves open models (Llama, Qwen, etc.) on custom hardware with very low latency.
- Its API is **OpenAI-compatible**. So if we talk to Groq through the
  OpenAI-style chat completions format, the same code also works with OpenAI,
  OpenRouter, Together, Ollama (local), and others by just changing the base
  URL. That's a cheap first step toward "any model".
- Free tier with rate limits; the key is read from the `GROQ_API_KEY`
  environment variable. The harness never stores it.
- Tests will use a **fake model**, so no key is needed to develop or test.

## Decision

- Provider: **Groq** (approved).
- Language: **Python** (approved).
  - The recommendation was TypeScript, mostly for distribution and UI reuse.
  - The project owner chose Python because it is their primary language and the
    goal is **learning agent design**, not learning a new language at the same time.
  - Hermes Agent (see [the landscape](ref-harness-landscape.md)) shows a popular,
    capable end-user harness can be built in Python.
  - What we accept: distribution needs care (we'll use a standard
    `pyproject.toml` so it installs with `pip`/`pipx`), and we must avoid
    blocking calls if we go async.
- Python version available: 3.12.

## What was done

Nothing yet beyond this write-up.

## How it was tested

Not applicable (decision record).

## What you should learn here

- **Choose a language for the shape of the work.** Here the work is I/O and
  JSON, so async + JSON ergonomics matter more than raw speed.
- **"Any language" is a boundary property.** Define clean protocols at the
  edges and the core's language stops limiting what can plug in.
- **Prefer standards with many implementations.** The OpenAI-compatible API
  turns one provider integration into many.
- **The "best" tool depends on the goal.** For learning, the language you
  already know beats the theoretically better one, because your attention goes to
  the new ideas instead of the syntax.

## Next

Once the language is chosen: entry 002 — Feature 1, the core agent loop.
