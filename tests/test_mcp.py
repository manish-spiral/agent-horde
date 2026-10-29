import json
import sys
from pathlib import Path

import pytest

from horde import cli
from horde.loop import run_tool
from horde.mcp import MCPServer, load_mcp_servers
from test_loop import FakeModel, answer, tool_call

FAKE_SERVER = str(Path(__file__).parent / "fixtures" / "fake_mcp_server.py")


@pytest.fixture
def server():
    server = MCPServer("fake", sys.executable, [FAKE_SERVER])
    yield server
    server.close()


def test_tools_are_listed_with_prefixed_names(server):
    tools = {tool.name: tool for tool in server.tools()}
    assert set(tools) == {"mcp__fake__echo", "mcp__fake__fail"}
    assert tools["mcp__fake__echo"].parameters["required"] == ["text"]
    assert tools["mcp__fake__fail"].parameters == {"type": "object", "properties": {}}
    assert all(tool.requires_approval({}) for tool in tools.values())


def test_calling_tools_through_the_loop(server):
    tools = {tool.name: tool for tool in server.tools()}
    allow = lambda name, args: True
    assert run_tool(tools, "mcp__fake__echo", '{"text": "hi"}', allow) == "hi"  # skips the notification
    assert run_tool(tools, "mcp__fake__fail", "{}", allow) == "Error: RuntimeError: it broke"
    assert run_tool(tools, "mcp__fake__echo", '{"text": "hi"}') == \
        "Error: the user did not allow mcp__fake__echo to run"


def test_server_errors_are_reported(server):
    with pytest.raises(RuntimeError, match="unknown resources/list"):
        server.request("resources/list")


def test_missing_config_means_no_servers(tmp_path):
    assert load_mcp_servers(tmp_path / "none.json") == []


def test_cli_gives_mcp_tools_to_the_agent(tmp_path, monkeypatch):
    config = tmp_path / "mcp.json"
    config.write_text(json.dumps({"mcpServers": {"fake": {"command": sys.executable,
                                                          "args": [FAKE_SERVER]}}}))
    fake = FakeModel([tool_call("mcp__fake__echo", {"text": "from mcp"}), answer("done")])
    monkeypatch.setattr(cli, "create_model", lambda *args: fake)
    monkeypatch.setattr("sys.argv", ["horde", "--mcp-config", str(config), "task"])
    monkeypatch.setattr("builtins.input", lambda: "y")

    assert cli.main() == 0
    assert fake.received[1][-1]["content"] == "from mcp"
