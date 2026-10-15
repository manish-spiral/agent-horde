"""`horde-trace`: look at or replay a saved trace."""

import argparse
import sys

from horde.builtin_tools import DEFAULT_TOOLS
from horde.cli import TerminalApprover
from horde.loop import LimitReached, run_agent
from horde.trace import ReplayModel, format_event, print_event, read_trace


def show(events: list[dict]) -> int:
    for event in events:
        line = format_event(event)
        if line:
            print(line)
        if event["type"] == "run_end" and event.get("answer") is not None:
            print(f"\nanswer:\n{event['answer']}")
    return 0


def replay(events: list[dict]) -> int:
    """Run the loop again, with the model's replies taken from the trace.

    Tools really run again (behind the usual approval prompt), so their results
    may differ from the recording. The model's replies do not.
    """
    start = next(event for event in events if event["type"] == "run_start")
    limits = start["limits"]
    try:
        answer = run_agent(start["task"], ReplayModel(events), DEFAULT_TOOLS,
                           max_steps=limits["max_steps"], max_tokens=limits["max_tokens"],
                           approve=TerminalApprover(), on_event=print_event)
    except (RuntimeError, LimitReached) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        return 130
    print(answer)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="horde-trace", description="Inspect a saved run.")
    parser.add_argument("command", choices=["show", "replay"],
                        help="show: print the timeline; replay: rerun it without calling the model")
    parser.add_argument("file", help="a trace file (.jsonl)")
    args = parser.parse_args()

    events = read_trace(args.file)
    return show(events) if args.command == "show" else replay(events)


if __name__ == "__main__":
    sys.exit(main())
