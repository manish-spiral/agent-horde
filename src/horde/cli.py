"""Command line entry point: `horde "your task"`."""

import argparse
import os
import sys
from pathlib import Path

from horde import builtin_tools
from horde.builtin_tools import DEFAULT_TOOLS
from horde.extensions import DEFAULT_TOOLS_DIR, load_tool_files
from horde.loop import LimitReached, new_conversation, run_agent
from horde.mcp import DEFAULT_MCP_CONFIG, load_mcp_servers
from horde.models import PROVIDERS, create_model
from horde.skills import (DEFAULT_SKILLS_DIR, load_skills, make_save_skill_tool,
                          make_skill_tool, skills_summary)
from horde.subagents import make_delegate_tool
from horde.session import DEFAULT_SESSION_DIR, load_session, new_session_id, save_session
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
    parser.add_argument("task", nargs="?",
                        help="what you want the agent to do (omit for an interactive chat)")
    parser.add_argument("--resume", metavar="SESSION",
                        help="continue a saved session ('last' for the most recent)")
    parser.add_argument("--session-dir", type=Path, default=DEFAULT_SESSION_DIR,
                        help=f"where sessions are saved (default: {DEFAULT_SESSION_DIR})")
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
    parser.add_argument("--tools-dir", type=Path, default=DEFAULT_TOOLS_DIR,
                        help=f"folder of your own tool files (default: {DEFAULT_TOOLS_DIR})")
    parser.add_argument("--skills-dir", type=Path, default=DEFAULT_SKILLS_DIR,
                        help=f"folder of skill files (default: {DEFAULT_SKILLS_DIR})")
    parser.add_argument("--mcp-config", type=Path, default=DEFAULT_MCP_CONFIG,
                        help=f"MCP servers to connect to (default: {DEFAULT_MCP_CONFIG})")
    args = parser.parse_args()

    try:
        model = create_model(args.provider, args.model, args.base_url)
        skills = load_skills(args.skills_dir)
        if args.resume:
            session_id, messages = load_session(args.session_dir, args.resume)
        else:
            instructions = [part for part in (project_instructions(),
                                              skills and skills_summary(skills)) if part]
            session_id, messages = new_session_id(), new_conversation("\n\n".join(instructions))
        servers = load_mcp_servers(args.mcp_config)
        extensions = load_tool_files(args.tools_dir)
        tools = DEFAULT_TOOLS + extensions + [tool for server in servers for tool in server.tools()]
        if skills:
            tools.append(make_skill_tool(skills))
        tools.append(make_save_skill_tool(args.skills_dir, skills))
    except (RuntimeError, OSError, ValueError) as error:  # bad setup: fail before creating a trace
        print(f"error: {error}", file=sys.stderr)
        return 1
    if skills:
        print(f"skills: {', '.join(skills)}", file=sys.stderr)
    if extensions:
        print(f"extensions: {', '.join(tool.name for tool in extensions)}", file=sys.stderr)
    if servers:
        print(f"mcp: {', '.join(server.name for server in servers)}", file=sys.stderr)
    trace = TraceWriter(args.trace_dir)
    approve = TerminalApprover()  # one per session, so "always" lasts the whole chat

    def on_event(event: dict) -> None:
        trace(event)
        print_event(event)

    tools = tools + [make_delegate_tool(model, tools, approve, on_event)]

    exit_code = 0
    try:
        for task in [args.task] if args.task else chat_turns():
            try:
                answer = run_agent(task, model, tools, max_steps=args.max_steps,
                                   max_seconds=args.max_seconds, max_tokens=args.max_tokens,
                                   approve=approve, on_event=on_event, messages=messages)
                print(answer)
            except (RuntimeError, LimitReached) as error:
                print(f"error: {error}", file=sys.stderr)
                exit_code = 1
            save_session(args.session_dir, session_id, messages)
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        exit_code = 130  # conventional exit code for Ctrl+C
    finally:
        for server in servers:
            server.close()
        save_session(args.session_dir, session_id, messages)
        trace.close()
        print(f"trace: {trace.path}", file=sys.stderr)
        print(f"session: {session_id} (resume with --resume {session_id})", file=sys.stderr)
    return exit_code


# Files whose contents are added to the system prompt, if found in the working directory.
INSTRUCTION_FILES = ("AGENTS.md", "HORDE.md")


def project_instructions() -> str | None:
    found = [Path(name) for name in INSTRUCTION_FILES if Path(name).is_file()]
    parts = [file.read_text(encoding="utf-8") for file in found]
    memory = builtin_tools.load_memory()
    if memory:
        found.append(builtin_tools.MEMORY_FILE)
        parts.append(f"Things you remembered from earlier sessions:\n{memory}")
    if not found:
        return None
    print(f"instructions: {', '.join(map(str, found))}", file=sys.stderr)
    return "\n\n".join(parts)


def chat_turns():
    """Read tasks from the terminal until 'exit', 'quit' or end of input."""
    while True:
        print("\n> ", end="", file=sys.stderr, flush=True)
        try:
            line = input().strip()
        except EOFError:
            return
        if line in ("exit", "quit"):
            return
        if line:
            yield line


if __name__ == "__main__":
    sys.exit(main())
