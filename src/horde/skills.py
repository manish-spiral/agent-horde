"""Skills: reusable instructions the agent loads only when it needs them.

A skill is a Markdown file in ~/.horde/skills/, e.g. `release.md`. Its first
non-empty line is the summary. The agent always sees the list of names and
summaries (cheap); it reads the full text with `use_skill` when a task matches.
"""

from pathlib import Path
from typing import Annotated

from horde.tools import Tool, tool

DEFAULT_SKILLS_DIR = Path.home() / ".horde" / "skills"


def load_skills(directory: Path) -> dict[str, str]:
    if not directory.is_dir():
        return {}
    return {file.stem: file.read_text(encoding="utf-8") for file in sorted(directory.glob("*.md"))}


def skills_summary(skills: dict[str, str]) -> str:
    lines = []
    for name, text in skills.items():
        summary = next((line.strip().lstrip("# ") for line in text.splitlines() if line.strip()), "")
        lines.append(f"- {name}: {summary}")
    return ("Skills you can load with use_skill when a task matches one:\n" + "\n".join(lines))


def make_skill_tool(skills: dict[str, str]) -> Tool:
    @tool
    def use_skill(name: Annotated[str, "The skill's name, from the skills list"]) -> str:
        """Load the full instructions of a skill. Follow them for the current task."""
        if name not in skills:
            raise ValueError(f"no skill '{name}'; available: {', '.join(skills)}")
        return skills[name]

    return use_skill
