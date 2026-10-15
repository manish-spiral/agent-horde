"""Traces: a record of everything that happened in a run.

A trace is a JSON Lines file, one event per line. Appending one line at a time
means a crash mid-run still leaves every earlier event readable.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

DEFAULT_TRACE_DIR = Path.home() / ".horde" / "traces"


class TraceWriter:
    """An `on_event` callback that appends each event to a new trace file."""

    def __init__(self, directory: Path = DEFAULT_TRACE_DIR):
        # Traces can contain file contents and command output: keep them private.
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = directory / f"{datetime.now():%Y-%m-%dT%H-%M-%S-%f}.jsonl"
        self.file = self.path.open("a", encoding="utf-8")

    def __call__(self, event: dict) -> None:
        stamped = {"time": datetime.now().isoformat(timespec="milliseconds"), **event}
        self.file.write(json.dumps(stamped) + "\n")
        self.file.flush()

    def close(self) -> None:
        self.file.close()


def read_trace(path: str | Path) -> list[dict]:
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


class ReplayModel:
    """Answers with the model replies recorded in a trace, in order. No API calls."""

    name = "replay"

    def __init__(self, events: list[dict]):
        self.replies = [(event["message"], event["usage"])
                        for event in events if event["type"] == "model_call"]

    def complete(self, messages: list[dict], tools: list[dict]) -> tuple[dict, dict]:
        if not self.replies:
            raise RuntimeError("the trace has no more recorded model replies")
        return self.replies.pop(0)


# --- showing events to a person ---------------------------------------------

def shorten(text: str, width: int = 200) -> str:
    """Squash whitespace onto one line and cut to `width` characters."""
    text = " ".join(str(text).split())
    return text if len(text) <= width else text[:width] + "…"


def format_event(event: dict) -> str | None:
    """One readable line per event (None for events not worth showing)."""
    kind = event["type"]
    if kind == "run_start":
        model = f" [{event['model']}]" if event.get("model") else ""
        return f"task{model}: {shorten(event['task'])}"
    if kind == "model_call":
        tokens = event["usage"].get("total_tokens")
        return (f"[step {event['step']}] model {event['duration']:.2f}s"
                + (f", {tokens} tokens" if tokens else ""))
    if kind == "tool_call":
        denied = " (denied)" if event["approval"] == "denied" else ""
        return (f"[step {event['step']}] {event['name']}({shorten(event['arguments'], 100)})"
                f"{denied} -> {shorten(event['result'])}")
    if kind == "run_end":
        reason = "" if event["outcome"] == "answer" else f": {event['error']}"
        return (f"{event['outcome']}{reason} — {event['steps']} steps, "
                f"{event['usage'].get('total_tokens', 0)} tokens, {event['elapsed']:.1f}s")
    return None


def print_event(event: dict) -> None:
    line = format_event(event)
    if line:
        print(line, file=sys.stderr)
