"""What every model adapter shares: the contract and the HTTP call."""

import time
from typing import Protocol

import httpx

# Rate limits (429) and server hiccups (5xx) are usually temporary: retry them.
RETRY_STATUSES = {408, 409, 429, 500, 502, 503, 504, 529}
RETRIES = 3
MAX_WAIT = 30.0


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
    for attempt in range(RETRIES + 1):
        response = None
        try:
            response = client.post(url, headers=headers, json=body)
        except httpx.TransportError as error:  # connection dropped, DNS, timeout...
            if attempt == RETRIES:
                raise RuntimeError(f"{provider} connection failed: {error}") from error
        else:
            if response.status_code not in RETRY_STATUSES or attempt == RETRIES:
                break
            if _retry_after(response) > MAX_WAIT:  # e.g. a daily limit: waiting won't help
                break
        time.sleep(_wait_seconds(response, attempt))
    if response.is_error:
        raise RuntimeError(f"{provider} API error {response.status_code}: {response.text}")
    return response.json()


def _retry_after(response: httpx.Response) -> float:
    try:
        return float(response.headers["retry-after"])
    except (KeyError, ValueError):
        return 0.0


def _wait_seconds(response: httpx.Response | None, attempt: int) -> float:
    """The server's retry-after if it gave one, else exponential backoff: 1, 2, 4 s."""
    wait = _retry_after(response) if response is not None else 0.0
    return wait if wait > 0 else float(2 ** attempt)
