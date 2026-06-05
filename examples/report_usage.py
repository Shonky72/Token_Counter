"""Drop-in helper: forward usage AND rate-limit headers to Token Counter.

Copy these functions into your project. Call ``report_call(...)`` right after
each LLM response — it forwards the response's rate-limit headers (so the tray
shows the provider's enforced limit/remaining/reset, live) and optionally the
token counts (for the ledger-based providers).

All calls are best-effort: failures never break your app.

Anthropic (the SDK exposes response headers via ``with_raw_response``)::

    raw = client.messages.with_raw_response.create(
        model="claude-opus-4-8", max_tokens=1024,
        messages=[{"role": "user", "content": "Hi"}])
    msg = raw.parse()
    report_call("claude", dict(raw.headers), model="claude-opus-4-8",
                input_tokens=msg.usage.input_tokens,
                output_tokens=msg.usage.output_tokens)

OpenAI::

    raw = client.chat.completions.with_raw_response.create(
        model="gpt-4o", messages=[{"role": "user", "content": "Hi"}])
    report_ratelimit("openai", dict(raw.headers))
"""

from __future__ import annotations

import json
import urllib.request

USAGE_URL = "http://127.0.0.1:8787/usage"
RATELIMIT_URL = "http://127.0.0.1:8787/ratelimit"


def _post(url: str, payload: dict, timeout: float = 2.0) -> bool:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status in (200, 202)
    except Exception:
        return False


def report_ratelimit(provider: str, headers: dict, scheme: str = "auto") -> bool:
    """Forward response headers so the tray reads the enforced limit live."""
    return _post(RATELIMIT_URL, {"provider": provider, "scheme": scheme, "headers": headers})


def report_call(
    provider: str,
    headers: dict | None = None,
    model: str | None = None,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_read_tokens: int = 0,
    cache_creation_tokens: int = 0,
    scheme: str = "auto",
) -> bool:
    """Forward both rate-limit headers and token counts in one call."""
    payload = {
        "provider": provider,
        "model": model or "unknown",
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_read_tokens": cache_read_tokens,
        "cache_creation_tokens": cache_creation_tokens,
        "scheme": scheme,
        "headers": headers or {},
    }
    return _post(USAGE_URL, payload)


if __name__ == "__main__":
    demo = {
        "anthropic-ratelimit-tokens-limit": "40000",
        "anthropic-ratelimit-tokens-remaining": "12000",
        "anthropic-ratelimit-tokens-reset": "2026-06-05T00:00:30Z",
    }
    ok = report_ratelimit("claude", demo)
    print("forwarded" if ok else "failed (is `token-counter run` active?)")
