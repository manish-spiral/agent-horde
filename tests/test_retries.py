import httpx
import pytest

from horde.models.base import RETRIES, post_json


@pytest.fixture
def waits(monkeypatch):
    slept = []
    monkeypatch.setattr("horde.models.base.time.sleep", slept.append)
    return slept


def client_answering(*responses):
    queue = list(responses)

    def handle(request):
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item
    return httpx.Client(transport=httpx.MockTransport(handle))


def test_rate_limit_is_retried_with_backoff(waits):
    client = client_answering(httpx.Response(429), httpx.Response(503),
                              httpx.Response(200, json={"ok": True}))
    assert post_json(client, "http://x", {}, {}, "test") == {"ok": True}
    assert waits == [1.0, 2.0]


def test_retry_after_header_is_respected(waits):
    client = client_answering(httpx.Response(429, headers={"retry-after": "7"}),
                              httpx.Response(200, json={}))
    post_json(client, "http://x", {}, {}, "test")
    assert waits == [7.0]


def test_connection_errors_are_retried(waits):
    client = client_answering(httpx.ConnectError("down"), httpx.Response(200, json={}))
    assert post_json(client, "http://x", {}, {}, "test") == {}
    assert waits == [1.0]


def test_gives_up_after_retries(waits):
    client = client_answering(*[httpx.Response(429, text="slow down")] * (RETRIES + 1))
    with pytest.raises(RuntimeError, match="test API error 429: slow down"):
        post_json(client, "http://x", {}, {}, "test")
    assert len(waits) == RETRIES


def test_client_errors_are_not_retried(waits):
    client = client_answering(httpx.Response(400, text="bad request"))
    with pytest.raises(RuntimeError, match="400"):
        post_json(client, "http://x", {}, {}, "test")
    assert waits == []
