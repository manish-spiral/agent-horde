"""Sessions: a conversation saved to disk so it can be resumed later.

A session file is the full message list as JSON, rewritten after every turn.
"""

import json
from datetime import datetime
from pathlib import Path

DEFAULT_SESSION_DIR = Path.home() / ".horde" / "sessions"


def new_session_id() -> str:
    return f"{datetime.now():%Y-%m-%dT%H-%M-%S-%f}"


def save_session(directory: Path, session_id: str, messages: list[dict]) -> Path:
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)  # may contain file contents
    path = directory / f"{session_id}.json"
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(messages, indent=1), encoding="utf-8")
    temporary.replace(path)  # atomic: a crash never leaves a half-written session
    return path


def load_session(directory: Path, session_id: str) -> tuple[str, list[dict]]:
    """Load a session by id, or the most recent one if the id is "last"."""
    if session_id == "last":
        files = sorted(directory.glob("*.json"))
        if not files:
            raise RuntimeError(f"no saved sessions in {directory}")
        session_id = files[-1].stem
    path = directory / f"{session_id}.json"
    if not path.exists():
        raise RuntimeError(f"no session '{session_id}' in {directory}")
    return session_id, json.loads(path.read_text(encoding="utf-8"))
