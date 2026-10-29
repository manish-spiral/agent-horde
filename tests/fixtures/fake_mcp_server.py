"""A tiny MCP server for tests: one `echo` tool, one `fail` tool, over stdio."""

import json
import sys

TOOLS = [
    {"name": "echo", "description": "Repeat the text.",
     "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}},
                     "required": ["text"]}},
    {"name": "fail", "description": "Always fails."},
]

for line in sys.stdin:
    message = json.loads(line)
    if "id" not in message:
        continue  # notification
    method, params = message["method"], message.get("params", {})
    if method == "initialize":
        result = {"protocolVersion": params["protocolVersion"], "capabilities": {"tools": {}},
                  "serverInfo": {"name": "fake", "version": "1"}}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call" and params["name"] == "echo":
        print(json.dumps({"jsonrpc": "2.0", "method": "notifications/progress"}), flush=True)
        result = {"content": [{"type": "text", "text": params["arguments"]["text"]}]}
    elif method == "tools/call":
        result = {"content": [{"type": "text", "text": "it broke"}], "isError": True}
    else:
        print(json.dumps({"jsonrpc": "2.0", "id": message["id"],
                          "error": {"code": -32601, "message": f"unknown {method}"}}), flush=True)
        continue
    print(json.dumps({"jsonrpc": "2.0", "id": message["id"], "result": result}), flush=True)
