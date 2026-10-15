"""Talk to Groq's chat completions API.

Groq's API is OpenAI-compatible, so this same request shape works with any
OpenAI-compatible server by changing the URL.
"""

import os

import httpx

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "openai/gpt-oss-120b"


class GroqModel:
    def __init__(self, model: str | None = None, api_key: str | None = None,
                 client: httpx.Client | None = None):
        self.model = model or os.environ.get("HORDE_MODEL", DEFAULT_MODEL)
        self.api_key = api_key or os.environ.get("GROQ_API_KEY")
        if not self.api_key:
            raise RuntimeError("GROQ_API_KEY is not set")
        self.client = client or httpx.Client(timeout=60.0)

    def complete(self, messages: list[dict], tools: list[dict]) -> tuple[dict, dict]:
        """Send the conversation so far. Returns (the model's next message, token usage)."""
        body = {"model": self.model, "messages": messages}
        if tools:
            body["tools"] = tools
        response = self.client.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {self.api_key}"},
            json=body,
        )
        if response.is_error:
            raise RuntimeError(f"Groq API error {response.status_code}: {response.text}")
        data = response.json()
        return data["choices"][0]["message"], data.get("usage", {})
