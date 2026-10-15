import json
import stat

import pytest

from horde import cli, trace_cli
from horde.builtin_tools import calculator
from horde.loop import StepLimitReached, TokenLimitReached, run_agent
from horde.tools import tool
from horde.trace import ReplayModel, TraceWriter, format_event, read_trace, shorten
from test_loop import FakeModel, answer, tool_call


def record(task, model, tools, **options):
    """Run the agent and return (answer or exception, events)."""
    events = []
    try:
        result = run_agent(task, model, tools, on_event=events.append, **options)
    except BaseException as error:
        result = error
    return result, events


# --- events -----------------------------------------------------------------

def test_events_describe_the_whole_run():
    model = FakeModel([tool_call("calculator", {"expression": "2+2"}), answer("4")],
                      usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15})
    result, events = record("add", model, [calculator])

    assert result == "4"
    assert [e["type"] for e in events] == \
        ["run_start", "model_call", "tool_call", "model_call", "run_end"]
    start, first_call, tool_event, _, end = events
    assert start["task"] == "add" and start["tools"] == ["calculator"]
    assert first_call["message"]["tool_calls"][0]["function"]["name"] == "calculator"
    assert tool_event["result"] == "4" and tool_event["approval"] == "not_needed"
    assert end["outcome"] == "answer" and end["answer"] == "4" and end["steps"] == 2
    assert end["usage"] == {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30}
    assert all("elapsed" in e for e in events)


@tool(needs_approval=True)
def risky() -> str:
    """Needs approval."""
    return "ran"


@pytest.mark.parametrize("allowed, expected", [(True, "approved"), (False, "denied")])
def test_approval_decision_is_recorded(allowed, expected):
    model = FakeModel([tool_call("risky", {}), answer("ok")])
    _, events = record("t", model, [risky], approve=lambda name, args: allowed)
    assert events[2]["approval"] == expected


def test_run_end_is_emitted_when_a_limit_stops_the_run():
    model = FakeModel([tool_call("calculator", {"expression": "1"})] * 2)
    result, events = record("t", model, [calculator], max_steps=2)
    assert isinstance(result, StepLimitReached)
    assert events[-1]["outcome"] == "step_limit" and events[-1]["steps"] == 2


def test_run_end_is_emitted_on_interrupt():
    class InterruptedModel:
        def complete(self, messages, tools):
            raise KeyboardInterrupt

    result, events = record("t", InterruptedModel(), [])
    assert isinstance(result, KeyboardInterrupt)
    assert events[-1]["outcome"] == "interrupted"


# --- token budget -----------------------------------------------------------

def test_token_budget_stops_the_run():
    model = FakeModel([tool_call("calculator", {"expression": "1"})] * 5,
                      usage={"total_tokens": 100})
    result, events = record("t", model, [calculator], max_tokens=150)
    assert isinstance(result, TokenLimitReached)
    assert len(model.received) == 2  # stopped before a third model call
    assert events[-1]["outcome"] == "token_limit"
    assert events[-1]["steps"] == 2  # counts model calls made, not the step that was refused


def test_final_answer_is_kept_even_if_it_crosses_the_budget():
    model = FakeModel([answer("done")], usage={"total_tokens": 500})
    result, _ = record("t", model, [], max_tokens=100)
    assert result == "done"


# --- trace file -------------------------------------------------------------

def test_trace_writer_writes_one_json_object_per_line(tmp_path):
    writer = TraceWriter(tmp_path / "traces")
    writer({"type": "run_start", "task": "a"})
    writer({"type": "run_end", "outcome": "answer"})
    writer.close()

    lines = writer.path.read_text().splitlines()
    assert len(lines) == 2 and all(json.loads(line) for line in lines)
    events = read_trace(writer.path)
    assert [e["type"] for e in events] == ["run_start", "run_end"]
    assert "time" in events[0]


def test_trace_directory_is_private(tmp_path):
    TraceWriter(tmp_path / "traces").close()
    assert stat.S_IMODE((tmp_path / "traces").stat().st_mode) == 0o700


def test_cli_saves_a_trace(monkeypatch, private_trace_dir):
    fake = FakeModel([tool_call("calculator", {"expression": "6*7"}), answer("42")])
    monkeypatch.setattr(cli, "GroqModel", lambda model=None: fake)
    monkeypatch.setattr("sys.argv", ["horde", "multiply"])

    assert cli.main() == 0
    [trace_file] = private_trace_dir.glob("*.jsonl")
    assert read_trace(trace_file)[-1]["answer"] == "42"


# --- display ----------------------------------------------------------------

def test_shorten_puts_text_on_one_line_and_cuts_it():
    assert shorten("a\n  b\tc") == "a b c"
    assert shorten("x" * 300, width=10) == "x" * 10 + "…"


def test_format_event_lines():
    assert format_event({"type": "tool_call", "step": 1, "name": "read_file",
                         "arguments": '{"path": "a"}', "approval": "denied",
                         "result": "Error: no"}) == \
        '[step 1] read_file({"path": "a"}) (denied) -> Error: no'
    assert format_event({"type": "run_end", "outcome": "answer", "steps": 2,
                         "usage": {"total_tokens": 30}, "elapsed": 1.25}) == \
        "answer — 2 steps, 30 tokens, 1.2s"


# --- replay -----------------------------------------------------------------

def test_replay_reproduces_a_recorded_run():
    model = FakeModel([tool_call("calculator", {"expression": "6*7"}), answer("42")])
    _, recorded = record("multiply", model, [calculator])

    result, replayed = record("multiply", ReplayModel(recorded), [calculator])

    assert result == "42"
    tool_events = lambda events: [(e["name"], e["arguments"], e["result"])
                                  for e in events if e["type"] == "tool_call"]
    assert tool_events(replayed) == tool_events(recorded)


def test_replay_model_runs_out_of_replies():
    with pytest.raises(RuntimeError, match="no more recorded model replies"):
        ReplayModel([]).complete([], [])


def write_trace(tmp_path, events):
    writer = TraceWriter(tmp_path)
    for event in events:
        writer(event)
    writer.close()
    return writer.path


def test_horde_trace_show_and_replay(tmp_path, monkeypatch, capsys):
    model = FakeModel([tool_call("calculator", {"expression": "6*7"}), answer("42")])
    _, events = record("multiply", model, [calculator])
    path = write_trace(tmp_path, events)

    monkeypatch.setattr("sys.argv", ["horde-trace", "show", str(path)])
    assert trace_cli.main() == 0
    out = capsys.readouterr().out
    assert "task: multiply" in out and "calculator" in out and "answer:\n42" in out

    monkeypatch.setattr("sys.argv", ["horde-trace", "replay", str(path)])
    assert trace_cli.main() == 0
    assert capsys.readouterr().out.strip() == "42"
