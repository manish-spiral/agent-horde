import json

import httpx
import pytest

from horde.groq import GroqModel
from horde.loop import StepLimitReached, run_agent
from horde.tools import calculate, calculator


class FakeModel:
    """Returns scripted replies in order and records what it was sent."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.received = []

    def complete(self, messages, tools):
        self.received.append([dict(m) for m in messages])
        return self.replies.pop(0)


def tool_call(name, arguments, call_id="call_1"):
    return {"role": "assistant", "content": None, "tool_calls": [{
        "id": call_id, "type": "function",
        "function": {"name": name, "arguments": json.dumps(arguments)},
    }]}


def answer(text):
    return {"role": "assistant", "content": text}


def test_returns_answer_when_no_tool_is_called():
    model = FakeModel([answer("hello")])
    assert run_agent("say hello", model, [calculator]) == "hello"


def test_runs_tool_and_feeds_result_back():
    model = FakeModel([tool_call("calculator", {"expression": "17 * 23 + 5"}), answer("396")])

    assert run_agent("what is 17*23+5?", model, [calculator]) == "396"

    second_request = model.received[1]
    assert second_request[-1] == {"role": "tool", "tool_call_id": "call_1", "content": "396"}


def test_unknown_tool_is_reported_to_model_not_raised():
    model = FakeModel([tool_call("nope", {}), answer("sorry")])

    assert run_agent("task", model, [calculator]) == "sorry"
    assert model.received[1][-1]["content"] == "Error: unknown tool 'nope'"


def test_tool_error_is_reported_to_model():
    model = FakeModel([tool_call("calculator", {"expression": "1/0"}), answer("can't")])

    run_agent("task", model, [calculator])
    assert model.received[1][-1]["content"].startswith("Error: ZeroDivisionError")


def test_stops_at_step_limit():
    model = FakeModel([tool_call("calculator", {"expression": "1+1"})] * 3)
    with pytest.raises(StepLimitReached):
        run_agent("loop forever", model, [calculator], max_steps=3)


def test_calculator_does_arithmetic_only():
    assert calculate("2 ** 10 - (3 * 4)") == "1012"
    with pytest.raises(ValueError):
        calculate("__import__('os').system('echo hi')")


def test_groq_request_shape():
    sent = {}

    def handler(request):
        sent["url"] = str(request.url)
        sent["auth"] = request.headers["authorization"]
        sent["body"] = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": answer("hi")}]})

    model = GroqModel(model="test-model", api_key="secret",
                      client=httpx.Client(transport=httpx.MockTransport(handler)))
    reply = model.complete([{"role": "user", "content": "hi"}], [calculator.schema()])

    assert reply == answer("hi")
    assert sent["url"] == "https://api.groq.com/openai/v1/chat/completions"
    assert sent["auth"] == "Bearer secret"
    assert sent["body"]["model"] == "test-model"
    assert sent["body"]["tools"][0]["function"]["name"] == "calculator"


def test_groq_error_includes_response_body():
    client = httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(401, text="invalid key")))
    model = GroqModel(api_key="bad", client=client)
    with pytest.raises(RuntimeError, match="401: invalid key"):
        model.complete([], [])
