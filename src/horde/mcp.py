"""MCP (Model Context Protocol) client: use tools from any MCP server.

An MCP server is a separate program, in any language, that offers tools. We
start it, talk JSON-RPC 2.0 over its stdin/stdout (one JSON message per line),
ask which tools it has (`tools/list`) and call them (`tools/call`).

Config uses the same shape as other harnesses:

    {"mcpServers": {"files": {"command": "npx", "args": ["-y", "some-server"], "env": {}}}}
"""

import json
import os
import subprocess
from pathlib import Path

from horde.tools import Tool

PROTOCOL_VERSION = "2025-06-18"
DEFAULT_MCP_CONFIG = Path.home() / ".horde" / "mcp.json"


class MCPServer:
    def __init__(self, name: str, command: str, args: list[str] | None = None,
                 env: dict | None = None):
        self.name = name
        self.process = subprocess.Popen(
            [command, *(args or [])], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, env={**os.environ, **(env or {})})
        self.next_id = 0
        self.request("initialize", {"protocolVersion": PROTOCOL_VERSION, "capabilities": {},
                                    "clientInfo": {"name": "agent-horde", "version": "0.1.0"}})
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def _send(self, message: dict) -> None:
        self.process.stdin.write(json.dumps(message) + "\n")
        self.process.stdin.flush()

    def request(self, method: str, params: dict | None = None) -> dict:
        self.next_id += 1
        self._send({"jsonrpc": "2.0", "id": self.next_id, "method": method, "params": params or {}})
        while True:  # skip notifications and anything that isn't our answer
            line = self.process.stdout.readline()
            if not line:
                raise RuntimeError(f"MCP server '{self.name}' closed the connection")
            message = json.loads(line)
            if message.get("id") == self.next_id and "method" not in message:
                break
        if "error" in message:
            raise RuntimeError(f"MCP server '{self.name}': {message['error'].get('message')}")
        return message.get("result") or {}

    def tools(self) -> list[Tool]:
        found, cursor = [], None
        while True:
            result = self.request("tools/list", {"cursor": cursor} if cursor else {})
            found += result.get("tools", [])
            cursor = result.get("nextCursor")
            if not cursor:
                break
        return [self._as_tool(spec) for spec in found]

    def _as_tool(self, spec: dict) -> Tool:
        def call(**arguments) -> str:
            return self.call(spec["name"], arguments)
        return Tool(
            name=f"mcp__{self.name}__{spec['name']}",
            description=spec.get("description", ""),
            parameters=spec.get("inputSchema") or {"type": "object", "properties": {}},
            function=call,
            needs_approval=True,  # outside code with unknown side effects: always ask
        )

    def call(self, tool_name: str, arguments: dict) -> str:
        result = self.request("tools/call", {"name": tool_name, "arguments": arguments})
        text = "\n".join(item.get("text", "") for item in result.get("content", [])
                         if item.get("type") == "text")
        if result.get("isError"):
            raise RuntimeError(text or "tool failed")
        return text

    def close(self) -> None:
        self.process.terminate()
        self.process.wait(timeout=5)


def load_mcp_servers(config_path: Path) -> list[MCPServer]:
    """Start every server in a config file. A missing file means no servers."""
    if not config_path.is_file():
        return []
    config = json.loads(config_path.read_text(encoding="utf-8"))
    return [MCPServer(name, entry["command"], entry.get("args"), entry.get("env"))
            for name, entry in config.get("mcpServers", {}).items()]
