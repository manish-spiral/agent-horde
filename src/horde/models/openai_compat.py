"""OpenAI chat completions format, used by OpenAI, Groq, OpenRouter, Ollama and many more.

This is also our internal format, so there is almost nothing to translate.
"""

import httpx

from horde.models.base import default_client, post_json


class OpenAICompatibleModel:
    def __init__(self, name: str, model: str, base_url: str, api_key: str | None = None,
                 client: httpx.Client | None = None):
        self.name = name
        self.model = model
        self.url = f"{base_url}/chat/completions"
        self.api_key = api_key
        self.client = client or default_client()

    def complete(self, messages: list[dict], tools: list[dict]) -> tuple[dict, dict]:
        # provider_state belongs to other adapters; strict servers reject unknown fields.
        clean = [{k: v for k, v in m.items() if k != "provider_state"} for m in messages]
        body = {"model": self.model, "messages": clean}
        if tools:
            body["tools"] = tools
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        data = post_json(self.client, self.url, headers, body, self.name)
        return data["choices"][0]["message"], data.get("usage") or {}
