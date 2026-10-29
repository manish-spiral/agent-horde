"""Extensions: your own tools, loaded from Python files in ~/.horde/tools/.

Each file defines tools with the same `@tool` decorator the built-in tools use.
Every Tool found at the top level of a file is added to the agent.

Only the user's own folder is loaded, never a project folder: these files are
code that runs on your machine.
"""

import importlib.util
from pathlib import Path

from horde.tools import Tool

DEFAULT_TOOLS_DIR = Path.home() / ".horde" / "tools"


def load_tool_files(directory: Path) -> list[Tool]:
    tools = []
    for file in sorted(directory.glob("*.py")) if directory.is_dir() else []:
        spec = importlib.util.spec_from_file_location(f"horde_extension_{file.stem}", file)
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception as error:
            raise RuntimeError(f"extension {file} failed to load: {error}") from error
        tools += [value for value in vars(module).values() if isinstance(value, Tool)]
    return tools
