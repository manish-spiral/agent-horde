# Reference — The agent harness landscape

A map of major agent harnesses and frameworks, and the language each is built in.
Based on knowledge as of mid-2026. Projects get rewritten, so check the repo
when it matters. "Closed" means not open source; the language there is inferred
from how it's distributed (e.g. npm, VS Code fork).

## 1. Coding agents — CLI / terminal

| Harness | Made by | Core language | Notes |
|---------|---------|---------------|-------|
| Claude Code | Anthropic | TypeScript | Closed; shipped via npm/native installer |
| Gemini CLI | Google | TypeScript | Open source |
| Qwen Code | Alibaba | TypeScript | Fork of Gemini CLI |
| Codex CLI | OpenAI | Rust | Started in TypeScript, rewritten in Rust |
| opencode | SST | TypeScript | Runs on Bun |
| Amp | Sourcegraph | TypeScript | |
| Aider | Community | Python | One of the earliest coding agents |
| Goose | Block | Rust | Desktop app UI in TypeScript/Electron |
| Crush | Charm | Go | |
| Plandex | Community | Go | |
| Open Interpreter | Community | Python | |

## 2. Coding agents — IDE / editor

| Harness | Core language | Notes |
|---------|---------------|-------|
| Cursor | TypeScript | Closed; VS Code fork |
| Cline | TypeScript | VS Code extension |
| Roo Code / Kilo Code | TypeScript | Cline forks |
| Continue | TypeScript | VS Code + JetBrains |
| GitHub Copilot agent mode | TypeScript | Closed; VS Code |
| Zed agent | Rust | Built into the Zed editor |

## 3. Autonomous / research agents

| Harness | Core language | Notes |
|---------|---------------|-------|
| OpenHands | Python | Web frontend in TypeScript |
| SWE-agent / mini-swe-agent | Python | Research, benchmarks (SWE-bench) |
| AutoGPT | Python | Frontend in TypeScript |
| MetaGPT | Python | Multi-agent "software company" |
| Letta (MemGPT) | Python | Focus on long-term memory |
| OpenClaw | TypeScript | Personal assistant agent |
| Hermes Agent (Nous Research) | Python | Self-improving: auto-creates skills, cross-session memory (SQLite FTS5), MCP, any model via OpenRouter/OpenAI/Anthropic, terminal + Telegram/Discord/Slack. MIT. A popular end-user agent written in Python, an exception to the pattern below |

## 4. Frameworks / SDKs (libraries for building agents)

| Framework | Languages | Notes |
|-----------|-----------|-------|
| LangChain / LangGraph | Python, TypeScript | |
| LlamaIndex | Python, TypeScript | Started as RAG |
| OpenAI Agents SDK | Python, TypeScript | |
| Claude Agent SDK | TypeScript, Python | The harness behind Claude Code |
| Google ADK | Python, Java (+ others) | |
| Microsoft Agent Framework / AutoGen / Semantic Kernel | Python, C# (.NET), Java (SK) | |
| AWS Strands Agents | Python, TypeScript | |
| Vercel AI SDK | TypeScript | |
| Mastra | TypeScript | |
| CrewAI | Python | Role-based multi-agent |
| smolagents | Python | Hugging Face; agents that write code |
| Pydantic AI | Python | |
| DSPy | Python | Optimizes prompts as programs |
| Rig | Rust | |
| Eino / LangChainGo | Go | |

## 5. Low-code / platform

| Platform | Languages |
|----------|-----------|
| n8n | TypeScript |
| Dify | Python backend, TypeScript frontend |
| Flowise | TypeScript |
| Langflow | Python backend, TypeScript frontend |

## The pattern

| Kind of project | Usual language | Why |
|-----------------|----------------|-----|
| Tools people **install and use** (CLIs, IDE extensions) | TypeScript | Easy distribution, UI reuse, IDEs run JS |
| Tools people **build with or research on** (frameworks, benchmarks) | Python | AI/ML ecosystem, researchers' default |
| Tools that must be a **fast single binary** with sandboxing | Rust / Go | Performance, safety, no runtime |
| Big frameworks | Python **and** TypeScript | They ship both to reach everyone |

Also notice that almost every project with a **web or desktop UI** uses TypeScript
for that part, even when its core is Python or Rust.
