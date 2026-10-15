"""Anthropic Messages API (Claude).

Differences from our internal (OpenAI) format:
- the system prompt is a top-level field, not a message
- content is a list of typed blocks: text, tool_use, thinking, ...
- tool results are `tool_result` blocks inside a *user* message, and all
  results for one assistant turn go in one message
- `max_tokens` is required
"""

import json

import httpx

from horde.models.base import default_client, post_json

API_VERSION = "2023-06-01"
MAX_TOKENS = 16000

# Models that accept server-side refusal fallbacks: if the model declines, the
# API retries on a fallback model inside the same call.
FALLBACK_MODELS = {"claude-fable-5-1", "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5"}


class AnthropicModel:
    def __init__(self, name: str, model: str, base_url: str, api_key: str | None = None,
                 client: httpx.Client | None = None):
        self.name = name
        self.model = model
        self.url = f"{base_url}/messages"
        self.api_key = api_key
        self.client = client or default_client()

    def complete(self, messages: list[dict], tools: list[dict]) -> tuple[dict, dict]:
        system, converted = to_anthropic(messages)
        body = {"model": self.model, "max_tokens": MAX_TOKENS, "messages": converted}
        if system:
            body["system"] = system
        if tools:
            body["tools"] = [{"name": t["function"]["name"],
                              "description": t["function"]["description"],
                              "input_schema": t["function"]["parameters"]} for t in tools]
        headers = {"x-api-key": self.api_key, "anthropic-version": API_VERSION}
        if self.model in FALLBACK_MODELS:
            headers["anthropic-beta"] = "server-side-fallback-2026-07-01"
            body["fallbacks"] = "default"
        return from_anthropic(post_json(self.client, self.url, headers, body, self.name))


def to_anthropic(messages: list[dict]) -> tuple[str, list[dict]]:
    system, converted = [], []

    def add(role: str, blocks: list[dict]):
        if converted and converted[-1]["role"] == role:
            converted[-1]["content"].extend(blocks)  # e.g. several tool results -> one message
        else:
            converted.append({"role": role, "content": list(blocks)})

    for message in messages:
        role = message["role"]
        if role == "system":
            system.append(message["content"])
        elif role == "user":
            add("user", [{"type": "text", "text": message["content"]}])
        elif role == "assistant":
            # Send Claude's own blocks back unchanged when we have them: they
            # include thinking blocks the API expects to see again.
            saved = (message.get("provider_state") or {}).get("anthropic")
            add("assistant", saved if saved is not None else _assistant_blocks(message))
        elif role == "tool":
            add("user", [{"type": "tool_result", "tool_use_id": message["tool_call_id"],
                          "content": message["content"]}])
    return "\n\n".join(system), converted


def _assistant_blocks(message: dict) -> list[dict]:
    blocks = [{"type": "text", "text": message["content"]}] if message.get("content") else []
    for call in message.get("tool_calls") or []:
        blocks.append({"type": "tool_use", "id": call["id"], "name": call["function"]["name"],
                       "input": json.loads(call["function"]["arguments"] or "{}")})
    return blocks


def from_anthropic(data: dict) -> tuple[dict, dict]:
    if data.get("stop_reason") == "refusal":
        category = (data.get("stop_details") or {}).get("category")
        raise RuntimeError(f"Claude declined the request (category: {category})")

    blocks = data.get("content") or []
    text = "".join(block["text"] for block in blocks if block["type"] == "text")
    tool_calls = [{"id": block["id"], "type": "function",
                   "function": {"name": block["name"], "arguments": json.dumps(block["input"])}}
                  for block in blocks if block["type"] == "tool_use"]
    message = {"role": "assistant", "content": text or None,
               "provider_state": {"anthropic": blocks}}
    if tool_calls:
        message["tool_calls"] = tool_calls

    usage = data.get("usage") or {}
    prompt = sum(usage.get(key) or 0 for key in
                 ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
    completion = usage.get("output_tokens") or 0
    return message, {"prompt_tokens": prompt, "completion_tokens": completion,
                     "total_tokens": prompt + completion}
