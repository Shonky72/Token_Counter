"""Drop-in helper: report token usage to a running Token Counter.

Copy ``report()`` into your project and call it right after each LLM response.
It is best-effort and non-blocking-ish: failures never break your app.

Anthropic example::

    import anthropic
    from report_usage import report

    client = anthropic.Anthropic()
    msg = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=1024,
        messages=[{"role": "user", "content": "Hello"}],
    )
    report("claude", "claude-opus-4-8",
           input_tokens=msg.usage.input_tokens,
           output_tokens=msg.usage.output_tokens,
           cache_read_tokens=getattr(msg.usage, "cache_read_input_tokens", 0) or 0,
           cache_creation_tokens=getattr(msg.usage, "cache_creation_input_tokens", 0) or 0)

Gemini example::

    resp = model.generate_content("Hello")
    um = resp.usage_metadata
    report("gemini", "gemini-1.5-pro",
           input_tokens=um.prompt_token_count,
           output_tokens=um.candidates_token_count)
"""

from __future__ import annotations

import json
import urllib.request

ENDPOINT = "http://127.0.0.1:8787/usage"


def report(
    provider: str,
    model: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_read_tokens: int = 0,
    cache_creation_tokens: int = 0,
    endpoint: str = ENDPOINT,
    timeout: float = 2.0,
) -> bool:
    """POST one usage record. Returns True on success, False on any failure."""
    body = json.dumps(
        {
            "provider": provider,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cache_read_tokens": cache_read_tokens,
            "cache_creation_tokens": cache_creation_tokens,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        endpoint, data=body, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status in (200, 202)
    except Exception:
        return False


if __name__ == "__main__":
    ok = report("claude", "claude-opus-4-8", input_tokens=1200, output_tokens=340)
    print("reported" if ok else "failed (is `token-counter run` active?)")
