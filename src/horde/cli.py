"""Command line entry point: `horde "your task"`."""

import argparse
import sys

from horde.groq import GroqModel
from horde.loop import StepLimitReached, run_agent
from horde.tools import calculator


def main() -> int:
    parser = argparse.ArgumentParser(prog="horde", description="Run an agent on a task.")
    parser.add_argument("task", help="what you want the agent to do")
    parser.add_argument("--model", help="model name (default: $HORDE_MODEL or a Groq default)")
    parser.add_argument("--max-steps", type=int, default=10)
    args = parser.parse_args()

    try:
        model = GroqModel(model=args.model)
        answer = run_agent(args.task, model, [calculator], max_steps=args.max_steps,
                           log=lambda line: print(line, file=sys.stderr))
    except (RuntimeError, StepLimitReached) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(answer)
    return 0


if __name__ == "__main__":
    sys.exit(main())
