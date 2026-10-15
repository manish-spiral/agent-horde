"""What every model adapter shares: the contract and the HTTP call."""

from typing import Protocol

import httpx


class Model(Protocol):
    """Anything the agent loop can think with.

    Messages and tools go in, and the reply comes out, in the OpenAI chat format
    (our internal format). Each adapter translates to and from its provider's
    own format. Usage is {prompt_tokens, completion_tokens, total_tokens}.

    An adapter may attach `provider_state` to the messages it returns: data
    only that provider understands (e.g. reasoning signatures) that must be
    sent back unchanged. The loop keeps it; other adapters ignore it.
    """

    name: str

    def complete(self, messages: list[dict], tools: list[dict]) -> tuple[dict, dict]: ...


def default_client() -> httpx.Client:
    # Reasoning models can think for minutes before replying.
    return httpx.Client(timeout=httpx.Timeout(600.0, connect=10.0))


def post_json(client: httpx.Client, url: str, headers: dict, body: dict, provider: str) -> dict:
    response = client.post(url, headers=headers, json=body)
    if response.is_error:
        raise RuntimeError(f"{provider} API error {response.status_code}: {response.text}")
    return response.json()
