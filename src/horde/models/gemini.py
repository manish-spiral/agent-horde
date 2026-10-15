"""Google Gemini API (generateContent).

Differences from our internal (OpenAI) format:
- messages are `contents` with role "user" or "model", each a list of `parts`
- the system prompt is a separate `systemInstruction`
- a tool call is a `functionCall` part; a result is a `functionResponse` part
  matched to its call by function *name* (ids are optional)
- reasoning models attach a `thoughtSignature` to parts, which must be sent
  back exactly as received
"""

import json
import uuid

import httpx

from horde.models.base import default_client, post_json

# Ids we invent for calls that came without one. Gemini never sees these.
GENERATED_ID_PREFIX = "horde_"


class GeminiModel:
    def __init__(self, name: str, model: str, base_url: str, api_key: str | None = None,
                 client: httpx.Client | None = None):
        self.name = name
        self.url = f"{base_url}/models/{model}:generateContent"
        self.api_key = api_key
        self.client = client or default_client()

    def complete(self, messages: list[dict], tools: list[dict]) -> tuple[dict, dict]:
        system, contents = to_gemini(messages)
        body = {"contents": contents}
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        if tools:
            body["tools"] = [{"functionDeclarations": [_declaration(t) for t in tools]}]
        headers = {"x-goog-api-key": self.api_key}
        return from_gemini(post_json(self.client, self.url, headers, body, self.name))


def _declaration(tool: dict) -> dict:
    function = tool["function"]
    declaration = {"name": function["name"], "description": function["description"]}
    if function["parameters"].get("properties"):  # Gemini rejects an empty object schema
        declaration["parameters"] = function["parameters"]
    return declaration


def to_gemini(messages: list[dict]) -> tuple[str, list[dict]]:
    system, contents, call_names = [], [], {}

    def add(role: str, parts: list[dict]):
        if contents and contents[-1]["role"] == role:
            contents[-1]["parts"].extend(parts)  # e.g. several results -> one turn
        else:
            contents.append({"role": role, "parts": list(parts)})

    for message in messages:
        role = message["role"]
        if role == "system":
            system.append(message["content"])
        elif role == "user":
            add("user", [{"text": message["content"]}])
        elif role == "assistant":
            for call in message.get("tool_calls") or []:
                call_names[call["id"]] = call["function"]["name"]
            # Send Gemini's own parts back unchanged when we have them: they
            # carry thought signatures.
            saved = (message.get("provider_state") or {}).get("gemini")
            add("model", saved if saved is not None else _model_parts(message))
        elif role == "tool":
            call_id = message["tool_call_id"]
            response = {"name": call_names.get(call_id, "unknown"),
                        "response": {"result": message["content"]}}
            if not call_id.startswith(GENERATED_ID_PREFIX):
                response["id"] = call_id
            add("user", [{"functionResponse": response}])
    return "\n\n".join(system), contents


def _model_parts(message: dict) -> list[dict]:
    parts = [{"text": message["content"]}] if message.get("content") else []
    for call in message.get("tool_calls") or []:
        parts.append({"functionCall": {"name": call["function"]["name"],
                                       "args": json.loads(call["function"]["arguments"] or "{}")}})
    return parts


def from_gemini(data: dict) -> tuple[dict, dict]:
    candidates = data.get("candidates") or []
    parts = ((candidates[0].get("content") or {}).get("parts") if candidates else None) or []
    if not parts:
        reason = (candidates[0].get("finishReason") if candidates
                  else (data.get("promptFeedback") or {}).get("blockReason"))
        raise RuntimeError(f"Gemini returned no content (reason: {reason})")

    text = "".join(part["text"] for part in parts if "text" in part and not part.get("thought"))
    tool_calls = []
    for part in parts:
        if "functionCall" in part:
            call = part["functionCall"]
            tool_calls.append({
                "id": call.get("id") or f"{GENERATED_ID_PREFIX}{uuid.uuid4().hex[:12]}",
                "type": "function",
                "function": {"name": call["name"], "arguments": json.dumps(call.get("args") or {})},
            })
    message = {"role": "assistant", "content": text or None, "provider_state": {"gemini": parts}}
    if tool_calls:
        message["tool_calls"] = tool_calls

    usage = data.get("usageMetadata") or {}
    prompt = usage.get("promptTokenCount") or 0
    total = usage.get("totalTokenCount") or prompt
    return message, {"prompt_tokens": prompt, "completion_tokens": total - prompt,
                     "total_tokens": total}
