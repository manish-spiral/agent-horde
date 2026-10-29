# 017 — Feature 16: Skills

## Goal

Reusable know-how ("how we cut a release", "how to review code here") the agent
can pull in when a task needs it, as in Claude Code and Hermes Agent, without
paying for it in every conversation.

## The big idea: progressive disclosure

Putting every instruction in the system prompt wastes context. Instead:
1. The system prompt lists only each skill's **name and one-line summary** (cheap).
2. When a task matches, the agent calls **`use_skill(name)`** to load the full text.

## Decisions

| Question | Choice and why |
|----------|----------------|
| Format | One Markdown file per skill in `~/.horde/skills/`: `name.md`. The first non-empty line (leading `#` stripped) is the summary. |
| Loading | Skills are read at startup; the list goes into new conversations, next to `AGENTS.md` and memory. |
| Tool | `use_skill` exists only when at least one skill exists. An unknown name gives an error listing the available skills. |
| Approval | None: reading instructions has no side effects. |
| Where from | The user's folder (or `--skills-dir`). Skills are instructions, so they're also an injection risk; same rule as extensions. |

## What was done

```
src/horde/skills.py      new: load_skills, skills_summary, make_skill_tool
src/horde/cli.py         --skills-dir; summary in the system prompt; use_skill tool
tests/conftest.py        tests never read the real ~/.horde/skills
tests/test_skills.py     new: 4 tests
```

## How it was tested

`uv run pytest` gives **105 passed** (101 + 4 new): summaries (blank lines and `#`
handled), full text loaded, unknown skill error, and the CLI putting the list in
the system prompt and serving `use_skill`. Not run live (Groq's daily limit was used up).

## Known gaps

- Hermes Agent also **writes** skills itself after hard tasks. Here skills are
  written by you. Letting the agent save skills (with approval) is a natural next step,
  combining this with `remember` ([013](013-long-term-memory.md)).

## What you should learn here

- **Progressive disclosure:** show a cheap index, and load details on demand.
  It's the same reason a book has a table of contents.
