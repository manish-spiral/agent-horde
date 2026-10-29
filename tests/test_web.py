import httpx
import pytest

from horde import builtin_tools
from horde.builtin_tools import html_to_text, web_fetch


def test_html_to_text_keeps_words_only():
    page = ("<html><head><style>p{}</style><script>alert(1)</script></head>"
            "<body><h1>Title</h1><p>Hello &amp; welcome<br>line two</p></body></html>")
    assert html_to_text(page) == "Title\nHello & welcome\nline two"


def test_web_fetch_needs_approval_and_http_urls():
    assert web_fetch.requires_approval({"url": "https://example.com"})
    with pytest.raises(ValueError, match="only http"):
        web_fetch.function("file:///etc/passwd")


def test_web_fetch_converts_html(monkeypatch):
    def fake_get(url, **options):
        return httpx.Response(200, headers={"content-type": "text/html"},
                              text="<p>Hi there</p>", request=httpx.Request("GET", url))
    monkeypatch.setattr(builtin_tools.httpx, "get", fake_get)
    assert web_fetch.function("https://example.com") == "Hi there"
