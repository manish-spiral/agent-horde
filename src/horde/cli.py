"""Command line entry point: `horde "your task"`."""

import argparse
import sys

from horde.builtin_tools import DEFAULT_TOOLS
from horde.groq import GroqModel
from horde.loop import StepLimitReached, run_agent

PREVIEW_CHARS = 1000


def ask_user(name: str, arguments: dict) -> bool:
    """Show a tool call on the terminal and ask whether it may run."""
    print(f"\nThe agent wants to run {name}:", file=sys.stderr)
    for key, value in arguments.items():
        text = str(value)
        if len(text) > PREVIEW_CHARS:
            text = text[:PREVIEW_CHARS] + f"... [{len(text) - PREVIEW_CHARS} more characters]"
        print(f"  {key}: {text}", file=sys.stderr)
    print("Allow? [y/N] ", end="", file=sys.stderr, flush=True)
    try:
        return input().strip().lower() in ("y", "yes")
    except EOFError:  # no interactive terminal: never allow
        return False


def main() -> int:
    parser = argparse.ArgumentParser(prog="horde", description="Run an agent on a task.")
    parser.add_argument("task", help="what you want the agent to do")
    parser.add_argument("--model", help="model name (default: $HORDE_MODEL or a Groq default)")
    parser.add_argument("--max-steps", type=int, default=10)
    args = parser.parse_args()

    try:
        model = GroqModel(model=args.model)
        answer = run_agent(args.task, model, DEFAULT_TOOLS, max_steps=args.max_steps,
                           approve=ask_user, log=lambda line: print(line, file=sys.stderr))
    except (RuntimeError, StepLimitReached) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(answer)
    return 0


if __name__ == "__main__":
    sys.exit(main())
