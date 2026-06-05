"""Lightweight, cheap credential probes used by the login screen.

Each probe hits a provider's *list models* endpoint (free, no generation) to
confirm a key works, and returns any rate-limit headers that came back so we can
seed the gauge immediately after sign-in.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

_TIMEOUT = 15


def _request(url: str, headers: dict, data: bytes | None = None) -> tuple[bool, str, dict]:
    req = urllib.request.Request(url, headers=headers, data=data)
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            resp.read()  # drain so the request completes
            return True, "ok", dict(resp.headers.items())
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            return False, "invalid credential (unauthorized)", {}
        # The rate-limit headers are present even on a 429/400 — keep them.
        return False, f"HTTP {exc.code}", dict(exc.headers.items()) if exc.headers else {}
    except (urllib.error.URLError, TimeoutError) as exc:
        return False, f"network error: {exc}", {}


def probe(scheme: str, api_key: str, base_url: str | None = None) -> tuple[bool, str, dict]:
    """Confirm a key works via the provider's cheap *list models* endpoint."""
    if not api_key.strip():
        return False, "empty credential", {}
    if scheme == "anthropic":
        url = (base_url or "https://api.anthropic.com").rstrip("/") + "/v1/models"
        return _request(url, {"x-api-key": api_key, "anthropic-version": "2023-06-01"})
    if scheme == "openai":
        url = (base_url or "https://api.openai.com/v1").rstrip("/") + "/models"
        return _request(url, {"Authorization": f"Bearer {api_key}"})
    if scheme == "google":
        return _request(
            f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}", {}
        )
    return True, "saved (no probe available for this scheme)", {}


# --- live rate-limit fetch (one tiny generation call) ----------------------
# A minimal request that returns the *token* rate-limit headers, so the gauge
# fills the moment a key is saved. Cost is a fraction of a cent.

def fetch_rate_limits(
    scheme: str, api_key: str, base_url: str | None = None, model: str | None = None
) -> tuple[bool, str, dict]:
    """Return (ok, message, headers) from a minimal live call for ``scheme``."""
    if scheme == "anthropic":
        url = (base_url or "https://api.anthropic.com").rstrip("/") + "/v1/messages"
        body = json.dumps({
            "model": model or "claude-3-5-haiku-latest",
            "max_tokens": 1,
            "messages": [{"role": "user", "content": "hi"}],
        }).encode()
        return _request(
            url,
            {"x-api-key": api_key, "anthropic-version": "2023-06-01",
             "content-type": "application/json"},
            data=body,
        )
    if scheme == "openai":
        url = (base_url or "https://api.openai.com/v1").rstrip("/") + "/chat/completions"
        body = json.dumps({
            "model": model or "gpt-4o-mini",
            "max_tokens": 1,
            "messages": [{"role": "user", "content": "hi"}],
        }).encode()
        return _request(
            url,
            {"Authorization": f"Bearer {api_key}", "content-type": "application/json"},
            data=body,
        )
    # Gemini and others: no live rate-limit headers.
    return False, "no live limits for this provider", {}
