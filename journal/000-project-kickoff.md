# 000 — Project kickoff

## Goal

Turn a broad intent ("an agent harness that can do everything") into a plan
we can start executing, without locking in an architecture too early.

## Context

The brief was intent, not a spec. Its rules:

- Ask before every action.
- Don't design a fixed architecture up front; build incrementally.
- Small, complete features, each tested and documented.
- Don't over-engineer.

The repo started empty. The project owner handles git (commits and pushes).

## Options considered

1. **Big design up front.** Draw the full architecture (memory system, planner,
   multi-agent orchestration…) and then build it.
   - Pro: feels thorough.
   - Con: we would be guessing. Most of those designs would be wrong in
     ways we can only discover by running real code.
2. **Intent + ordered roadmap.** Write down *what* the harness should be able
   to do and in what order, but decide *how* only when we reach each feature.
   - Pro: every decision is made with real code and real feedback in hand.
   - Con: some refactoring later. That's an acceptable, normal cost.

## Decision

Option 2. See [PLAN.md](../PLAN.md).

### Why this feature order?

The order follows **dependency and risk**:

- **Core loop first** (1): nothing else matters until a model can call a tool
  and react to the result. This is the heart of every agent.
- **Tools, safety, observability next** (2–4): once the agent can *act*, it
  must be controllable and visible *before* it gets more powerful.
- **Second provider** (5): we only build a "model abstraction" once we have two
  real models to abstract over. Before that, any abstraction is guesswork.
- **Memory, self-correction, planning** (6–8): these make it smarter, and
  they all build on the loop plus trace.
- **MCP, long-term memory, feedback, sub-agents, extensions** (9–13): these
  make it open-ended, which is the "no fixed ceiling" part of the intent.

## What was done

- Created `PLAN.md` (intent, principles, roadmap, decisions).
- Created `journal/` (this learning log).

## How it was tested

No code yet. The plan was reviewed and approved by the project owner.

## What you should learn here

- **Write intent before architecture.** Intent ("what and why") stays stable;
  architecture ("how") should change as you learn.
- **Order work by dependency and risk.** Build what everything else depends
  on first, and add safety before adding power.
- **YAGNI ("You Aren't Gonna Need It").** Don't build abstractions for needs
  you only imagine. Wait until you have two real cases.
- **Keep a decision log.** Six months from now, "why did we do it this way?"
  is answered by a file, not by memory.

## Next

[001 — Choosing a language and model provider](001-language-choice.md)
