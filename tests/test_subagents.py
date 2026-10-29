from horde import cli
from horde.builtin_tools import calculator
from horde.loop import run_agent
from horde.subagents import make_delegate_tool
from test_loop import FakeModel, answer, tool_call


def test_delegate_runs_a_helper_with_a_fresh_context():
    # Parent asks for help; the helper (same fake model) answers; parent finishes.
    model = FakeModel([tool_call("delegate", {"task": "find the answer"}),
                       answer("helper says 42"), answer("the answer is 42")])
    events = []
    delegate = make_delegate_tool(model, [calculator], lambda n, a: False, events.append)

    result = run_agent("main task", model, [calculator, delegate], on_event=events.append)

    assert result == "the answer is 42"
    helper_request = model.received[1]
    assert [m["role"] for m in helper_request] == ["system", "user"]  # fresh context
    assert helper_request[1]["content"] == "find the answer"
    assert model.received[2][-1]["content"] == "helper says 42"  # answer came back as tool result
    assert [e["type"] for e in events if e.get("subagent")] == ["run_start", "model_call", "run_end"]


def test_helper_cannot_delegate_further():
    model = FakeModel([tool_call("delegate", {"task": "again"}), answer("stop")])
    delegate = make_delegate_tool(model, [calculator], lambda n, a: False, lambda e: None)
    assert delegate.function("sub task") == "stop"
    assert model.received[1][-1]["content"] == "Error: unknown tool 'delegate'"


def test_cli_offers_delegate(monkeypatch):
    fake = FakeModel([answer("ok")])
    seen = {}

    def spy(task, model, tools, **options):
        seen["tools"] = [tool.name for tool in tools]
        return "ok"
    monkeypatch.setattr(cli, "create_model", lambda *args: fake)
    monkeypatch.setattr(cli, "run_agent", spy)
    monkeypatch.setattr("sys.argv", ["horde", "task"])
    assert cli.main() == 0
    assert seen["tools"][-1] == "delegate"
