"""Command line entry point: `horde "your task"`."""

import argparse
import sys

from horde.builtin_tools import DEFAULT_TOOLS
from horde.groq import GroqModel
from horde.loop import LimitReached, run_agent

PREVIEW_CHARS = 1000


class TerminalApprover:
    """Asks on the terminal before a tool runs. Remembers "always" for this run only."""

    def __init__(self):
        self.always_allowed: set[str] = set()

    def __call__(self, name: str, arguments: dict) -> bool:
        if name in self.always_allowed:
            return True
        print(f"\nThe agent wants to run {name}:", file=sys.stderr)
        for key, value in arguments.items():
            text = str(value)
            if len(text) > PREVIEW_CHARS:
                text = text[:PREVIEW_CHARS] + f"... [{len(text) - PREVIEW_CHARS} more characters]"
            print(f"  {key}: {text}", file=sys.stderr)
        print("Allow? [y]es / [n]o / [a]lways for this run: ", end="", file=sys.stderr, flush=True)
        try:
            answer = input().strip().lower()
        except EOFError:  # no interactive terminal: never allow
            return False
        if answer in ("a", "always"):
            self.always_allowed.add(name)
            return True
        return answer in ("y", "yes")


def main() -> int:
    parser = argparse.ArgumentParser(prog="horde", description="Run an agent on a task.")
    parser.add_argument("task", help="what you want the agent to do")
    parser.add_argument("--model", help="model name (default: $HORDE_MODEL or a Groq default)")
    parser.add_argument("--max-steps", type=int, default=10)
    parser.add_argument("--max-seconds", type=float, help="stop if no answer after this long")
    args = parser.parse_args()

    try:
        model = GroqModel(model=args.model)
        answer = run_agent(args.task, model, DEFAULT_TOOLS, max_steps=args.max_steps,
                           max_seconds=args.max_seconds, approve=TerminalApprover(),
                           log=lambda line: print(line, file=sys.stderr))
    except (RuntimeError, LimitReached) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        return 130  # conventional exit code for Ctrl+C

    print(answer)
    return 0


if __name__ == "__main__":
    sys.exit(main())
