"""Adapter tests: a fake network records each request and returns a canned reply."""

import json

import httpx
import pytest

from horde.builtin_tools import calculator, read_file
from horde.models import PROVIDERS, create_model
from horde.models.gemini import GENERATED_ID_PREFIX
from horde.tools import tool


class FakeServer:
    """Records requests and answers each one with the next canned JSON response."""

    def __init__(self, *responses, status=200):
        self.responses = list(responses)
        self.status = status
        self.requests = []

    def handle(self, request):
        self.requests.append(request)
        return httpx.Response(self.status, json=self.responses.pop(0))

    @property
    def client(self):
        return httpx.Client(transport=httpx.MockTransport(self.handle))

    def body(self, index=-1):
        return json.loads(self.requests[index].content)


@pytest.fixture
def keys(monkeypatch):
    for settings in PROVIDERS.values():
        if settings.key_env:
            monkeypatch.setenv(settings.key_env, "secret")
    monkeypatch.delenv("HORDE_MODEL", raising=False)


# A conversation in our internal format: one tool call, one result.
CONVERSATION = [
    {"role": "system", "content": "be helpful"},
    {"role": "user", "content": "what is 2+2?"},
    {"role": "assistant", "content": "Let me check.", "tool_calls": [{
        "id": "call_1", "type": "function",
        "function": {"name": "calculator", "arguments": '{"expression": "2+2"}'}}]},
    {"role": "tool", "tool_call_id": "call_1", "content": "4"},
]
TOOLS = [calculator.schema()]


# --- creating models --------------------------------------------------------

def test_create_model_uses_provider_defaults(keys):
    model = create_model("groq")
    assert model.name == "groq:openai/gpt-oss-120b"
    assert create_model("anthropic").name == "anthropic:claude-opus-5-5"


def test_create_model_errors_are_clear(keys, monkeypatch):
    with pytest.raises(RuntimeError, match="unknown provider 'nope'"):
        create_model("nope")
    with pytest.raises(RuntimeError, match="no default model"):
        create_model("openai")
    with pytest.raises(RuntimeError, match="needs --base-url"):
        create_model("custom", model="m")
    monkeypatch.delenv("OPENAI_API_KEY")
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY is not set"):
        create_model("openai", model="m")


def test_model_can_come_from_environment(keys, monkeypatch):
    monkeypatch.setenv("HORDE_MODEL", "from-env")
    assert create_model("openai").name == "openai:from-env"


def test_ollama_needs_no_key(monkeypatch):
    monkeypatch.delenv("HORDE_MODEL", raising=False)
    assert create_model("ollama", model="llama3").name == "ollama:llama3"


# --- OpenAI-compatible ------------------------------------------------------

def test_openai_compatible_request_and_reply(keys):
    server = FakeServer({"choices": [{"message": {"role": "assistant", "content": "4"}}],
                         "usage": {"total_tokens": 42}})
    model = create_model("groq", client=server.client)
    with_state = CONVERSATION + [{"role": "assistant", "content": "x",
                                  "provider_state": {"gemini": []}}]

    message, usage = model.complete(with_state, TOOLS)

    request = server.requests[0]
    assert str(request.url) == "https://api.groq.com/openai/v1/chat/completions"
    assert request.headers["authorization"] == "Bearer secret"
    body = server.body()
    assert body["model"] == "openai/gpt-oss-120b"
    assert body["tools"] == TOOLS
    assert all("provider_state" not in m for m in body["messages"])
    assert message == {"role": "assistant", "content": "4"} and usage == {"total_tokens": 42}


def test_openai_compatible_without_key_sends_no_auth(monkeypatch):
    monkeypatch.delenv("HORDE_API_KEY", raising=False)
    server = FakeServer({"choices": [{"message": {"role": "assistant", "content": "hi"}}]})
    model = create_model("custom", model="m", base_url="http://localhost:8000/v1/",
                         client=server.client)
    model.complete([{"role": "user", "content": "hi"}], [])
    assert str(server.requests[0].url) == "http://localhost:8000/v1/chat/completions"
    assert "authorization" not in server.requests[0].headers


def test_api_errors_include_the_response_body(keys):
    server = FakeServer({"error": "invalid key"}, status=401)
    model = create_model("groq", client=server.client)
    with pytest.raises(RuntimeError, match='groq:openai/gpt-oss-120b API error 401: .*invalid key'):
        model.complete([], [])


# --- Anthropic --------------------------------------------------------------

ANTHROPIC_REPLY = {
    "content": [
        {"type": "thinking", "thinking": "", "signature": "sig"},
        {"type": "text", "text": "Reading it."},
        {"type": "tool_use", "id": "toolu_1", "name": "read_file", "input": {"path": "a.txt"}},
    ],
    "stop_reason": "tool_use",
    "usage": {"input_tokens": 10, "cache_read_input_tokens": 5, "output_tokens": 7},
}


def test_anthropic_request_shape(keys):
    server = FakeServer(ANTHROPIC_REPLY)
    create_model("anthropic", client=server.client).complete(CONVERSATION, TOOLS)

    request = server.requests[0]
    assert str(request.url) == "https://api.anthropic.com/v1/messages"
    assert request.headers["x-api-key"] == "secret"
    assert request.headers["anthropic-version"] == "2023-06-01"
    body = server.body()
    assert body["model"] == "claude-opus-5-5" and body["max_tokens"] > 0
    assert body["system"] == "be helpful"
    assert body["tools"] == [{"name": "calculator", "description": calculator.description,
                              "input_schema": calculator.parameters}]
    assert body["messages"] == [
        {"role": "user", "content": [{"type": "text", "text": "what is 2+2?"}]},
        {"role": "assistant", "content": [
            {"type": "text", "text": "Let me check."},
            {"type": "tool_use", "id": "call_1", "name": "calculator",
             "input": {"expression": "2+2"}}]},
        {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "call_1", "content": "4"}]},
    ]


def test_anthropic_fallbacks_only_for_models_that_support_them(keys):
    server = FakeServer(ANTHROPIC_REPLY, ANTHROPIC_REPLY)
    create_model("anthropic", client=server.client).complete(CONVERSATION, [])
    assert server.body(0)["fallbacks"] == "default"
    assert server.requests[0].headers["anthropic-beta"] == "server-side-fallback-2026-07-01"

    create_model("anthropic", model="claude-haiku-4-5", client=server.client).complete(
        CONVERSATION, [])
    assert "fallbacks" not in server.body(1)
    assert "anthropic-beta" not in server.requests[1].headers


def test_anthropic_reply_is_translated(keys):
    server = FakeServer(ANTHROPIC_REPLY)
    message, usage = create_model("anthropic", client=server.client).complete(CONVERSATION, [])

    assert message["content"] == "Reading it."
    assert message["tool_calls"] == [{"id": "toolu_1", "type": "function", "function": {
        "name": "read_file", "arguments": '{"path": "a.txt"}'}}]
    assert message["provider_state"] == {"anthropic": ANTHROPIC_REPLY["content"]}
    assert usage == {"prompt_tokens": 15, "completion_tokens": 7, "total_tokens": 22}


def test_anthropic_sends_its_own_blocks_back_unchanged(keys):
    server = FakeServer(ANTHROPIC_REPLY, ANTHROPIC_REPLY)
    model = create_model("anthropic", client=server.client)
    message, _ = model.complete(CONVERSATION[:2], [read_file.schema()])

    two_results = CONVERSATION[:2] + [
        message,
        {"role": "tool", "tool_call_id": "toolu_1", "content": "file text"},
        {"role": "tool", "tool_call_id": "toolu_2", "content": "other"},
    ]
    model.complete(two_results, [read_file.schema()])

    sent = server.body(1)["messages"]
    assert sent[1] == {"role": "assistant", "content": ANTHROPIC_REPLY["content"]}  # thinking kept
    assert [b["tool_use_id"] for b in sent[2]["content"]] == ["toolu_1", "toolu_2"]  # one message


def test_anthropic_refusal_is_an_error(keys):
    server = FakeServer({"content": [], "stop_reason": "refusal",
                         "stop_details": {"type": "refusal", "category": "cyber"}})
    with pytest.raises(RuntimeError, match="declined.*cyber"):
        create_model("anthropic", client=server.client).complete(CONVERSATION, [])


# --- Gemini -----------------------------------------------------------------

GEMINI_REPLY = {
    "candidates": [{"content": {"role": "model", "parts": [
        {"text": "thinking about it", "thought": True},
        {"text": "Reading it."},
        {"functionCall": {"name": "read_file", "args": {"path": "a.txt"}},
         "thoughtSignature": "sig=="},
    ]}, "finishReason": "STOP"}],
    "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 4, "totalTokenCount": 20},
}


def test_gemini_request_shape(keys):
    @tool
    def no_args() -> str:
        """Takes nothing."""
        return ""

    server = FakeServer(GEMINI_REPLY)
    create_model("gemini", model="gemini-test", client=server.client).complete(
        CONVERSATION, TOOLS + [no_args.schema()])

    request = server.requests[0]
    assert str(request.url) == ("https://generativelanguage.googleapis.com/v1beta/"
                                "models/gemini-test:generateContent")
    assert request.headers["x-goog-api-key"] == "secret"
    body = server.body()
    assert body["systemInstruction"] == {"parts": [{"text": "be helpful"}]}
    assert body["tools"] == [{"functionDeclarations": [
        {"name": "calculator", "description": calculator.description,
         "parameters": calculator.parameters},
        {"name": "no_args", "description": "Takes nothing."},  # no empty schema
    ]}]
    assert body["contents"] == [
        {"role": "user", "parts": [{"text": "what is 2+2?"}]},
        {"role": "model", "parts": [
            {"text": "Let me check."},
            {"functionCall": {"name": "calculator", "args": {"expression": "2+2"}}}]},
        {"role": "user", "parts": [{"functionResponse": {
            "name": "calculator", "id": "call_1", "response": {"result": "4"}}}]},
    ]


def test_gemini_reply_is_translated(keys):
    server = FakeServer(GEMINI_REPLY)
    message, usage = create_model("gemini", model="g", client=server.client).complete(
        CONVERSATION, [])

    assert message["content"] == "Reading it."  # thought parts are not part of the answer
    [call] = message["tool_calls"]
    assert call["id"].startswith(GENERATED_ID_PREFIX)
    assert call["function"] == {"name": "read_file", "arguments": '{"path": "a.txt"}'}
    assert message["provider_state"] == {"gemini": GEMINI_REPLY["candidates"][0]["content"]["parts"]}
    assert usage == {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20}


def test_gemini_sends_its_own_parts_back_unchanged(keys):
    server = FakeServer(GEMINI_REPLY, GEMINI_REPLY)
    model = create_model("gemini", model="g", client=server.client)
    message, _ = model.complete(CONVERSATION[:2], [])
    call_id = message["tool_calls"][0]["id"]

    model.complete(CONVERSATION[:2] + [
        message, {"role": "tool", "tool_call_id": call_id, "content": "file text"}], [])

    contents = server.body(1)["contents"]
    assert contents[1]["parts"] == GEMINI_REPLY["candidates"][0]["content"]["parts"]  # signature kept
    assert contents[2]["parts"] == [{"functionResponse": {  # invented id is not sent
        "name": "read_file", "response": {"result": "file text"}}}]


def test_gemini_empty_reply_is_an_error(keys):
    server = FakeServer({"candidates": [{"finishReason": "SAFETY"}]})
    with pytest.raises(RuntimeError, match="no content.*SAFETY"):
        create_model("gemini", model="g", client=server.client).complete(CONVERSATION, [])
