"""Lightweight, cheap credential probes used by the login screen.

Each probe hits a provider's *list models* endpoint (free, no generation) to
confirm a key works, and returns any rate-limit headers that came back so we can
seed the gauge immediately after sign-in.
"""

from __future__ import annotations

import urllib.error
import urllib.request

_TIMEOUT = 12


def _request(url: str, headers: dict) -> tuple[bool, str, dict]:
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            resp.read(1)  # touch the body so the request completes
            return True, "ok", dict(resp.headers.items())
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            return False, "invalid credential (unauthorized)", {}
        return False, f"HTTP {exc.code}", dict(exc.headers.items()) if exc.headers else {}
    except (urllib.error.URLError, TimeoutError) as exc:
        return False, f"network error: {exc}", {}


def probe_anthropic(api_key: str) -> tuple[bool, str, dict]:
    return _request(
        "https://api.anthropic.com/v1/models",
        {"x-api-key": api_key, "anthropic-version": "2023-06-01"},
    )


def probe_openai(api_key: str) -> tuple[bool, str, dict]:
    return _request(
        "https://api.openai.com/v1/models",
        {"Authorization": f"Bearer {api_key}"},
    )


def probe_google(api_key: str) -> tuple[bool, str, dict]:
    return _request(
        f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}",
        {},
    )


PROBES = {
    "anthropic": probe_anthropic,
    "openai": probe_openai,
    "google": probe_google,
}


def probe(scheme: str, api_key: str) -> tuple[bool, str, dict]:
    fn = PROBES.get(scheme)
    if fn is None:
        if api_key.strip():
            return True, "saved (no probe available for this scheme)", {}
        return False, "empty credential", {}
    return fn(api_key)
