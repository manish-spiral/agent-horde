"""Command line entry point: `horde "your task"`."""

import argparse
import os
import sys
from pathlib import Path

from horde.builtin_tools import DEFAULT_TOOLS
from horde.loop import LimitReached, run_agent
from horde.models import PROVIDERS, create_model
from horde.trace import DEFAULT_TRACE_DIR, TraceWriter, print_event

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
    parser.add_argument("--provider", choices=list(PROVIDERS),
                        default=os.environ.get("HORDE_PROVIDER", "groq"),
                        help="model provider (default: $HORDE_PROVIDER or groq)")
    parser.add_argument("--model", help="model name (default: $HORDE_MODEL or the provider's default)")
    parser.add_argument("--base-url", help="override the provider's API address")
    parser.add_argument("--max-steps", type=int, default=10)
    parser.add_argument("--max-seconds", type=float, help="stop if no answer after this long")
    parser.add_argument("--max-tokens", type=int, help="stop once this many tokens are used")
    parser.add_argument("--trace-dir", type=Path, default=DEFAULT_TRACE_DIR,
                        help=f"where to save the run's trace (default: {DEFAULT_TRACE_DIR})")
    args = parser.parse_args()

    try:
        model = create_model(args.provider, args.model, args.base_url)
    except RuntimeError as error:  # bad setup: fail before creating a trace
        print(f"error: {error}", file=sys.stderr)
        return 1
    trace = TraceWriter(args.trace_dir)

    def on_event(event: dict) -> None:
        trace(event)
        print_event(event)

    try:
        answer = run_agent(args.task, model, DEFAULT_TOOLS, max_steps=args.max_steps,
                           max_seconds=args.max_seconds, max_tokens=args.max_tokens,
                           approve=TerminalApprover(), on_event=on_event)
    except (RuntimeError, LimitReached) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        return 130  # conventional exit code for Ctrl+C
    finally:
        trace.close()
        print(f"trace: {trace.path}", file=sys.stderr)

    print(answer)
    return 0


if __name__ == "__main__":
    sys.exit(main())
