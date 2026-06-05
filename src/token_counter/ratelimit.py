"""Parse provider rate-limit response headers into a normalized shape.

This is how "provider-enforced limits" enter the app: your code forwards the
headers from each real API response, and we read the provider's own
limit/remaining/reset off them — nothing is configured by hand.

Two header schemes are understood, auto-detected by prefix:

  Anthropic (``anthropic-ratelimit-*``):
    anthropic-ratelimit-requests-limit / -remaining / -reset
    anthropic-ratelimit-tokens-limit   / -remaining / -reset
    anthropic-ratelimit-input-tokens-* / -output-tokens-*
    (reset values are RFC3339 timestamps)

  OpenAI (``x-ratelimit-*``):
    x-ratelimit-limit-requests   / x-ratelimit-remaining-requests / x-ratelimit-reset-requests
    x-ratelimit-limit-tokens     / x-ratelimit-remaining-tokens   / x-ratelimit-reset-tokens
    (reset values are durations like "6m0s" or "1.5s")

Normalized output: ``{window_name: {"limit": int|None, "remaining": int|None,
"reset_at": epoch_float|None, "unit": "tokens"|"requests"}}``.
"""

from __future__ import annotations

import re
import time
from datetime import datetime, timezone


def _to_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_rfc3339(value: str) -> float | None:
    """Anthropic reset timestamps, e.g. '2026-06-04T12:34:56Z' -> epoch."""
    if not value:
        return None
    try:
        v = value.strip().replace("Z", "+00:00")
        return datetime.fromisoformat(v).timestamp()
    except ValueError:
        return None


_DURATION_RE = re.compile(r"(\d+(?:\.\d+)?)(ms|s|m|h|d)")


def _parse_duration(value: str, now: float | None = None) -> float | None:
    """OpenAI reset durations, e.g. '6m0s', '1.5s', '500ms' -> absolute epoch."""
    if value is None:
        return None
    value = str(value).strip()
    now = now if now is not None else time.time()
    # Bare number => seconds.
    try:
        return now + float(value)
    except ValueError:
        pass
    units = {"ms": 0.001, "s": 1, "m": 60, "h": 3600, "d": 86400}
    matches = _DURATION_RE.findall(value)
    if not matches:
        return None
    seconds = sum(float(num) * units[unit] for num, unit in matches)
    return now + seconds


def _lower(headers: dict) -> dict:
    return {str(k).lower(): v for k, v in headers.items()}


def _window(limit, remaining, reset, unit, reset_parser) -> dict:
    return {
        "limit": _to_int(limit),
        "remaining": _to_int(remaining),
        "reset_at": reset_parser(reset) if reset is not None else None,
        "unit": unit,
    }


def detect_scheme(headers: dict) -> str | None:
    h = _lower(headers)
    if any(k.startswith("anthropic-ratelimit-") for k in h):
        return "anthropic"
    if any(k.startswith("x-ratelimit-") for k in h):
        return "openai"
    return None


def _parse_anthropic(h: dict) -> dict:
    windows: dict[str, dict] = {}
    specs = [
        ("requests", "requests", "requests"),
        ("tokens", "tokens", "tokens"),
        ("input-tokens", "input_tokens", "tokens"),
        ("output-tokens", "output_tokens", "tokens"),
    ]
    for hdr, name, unit in specs:
        limit = h.get(f"anthropic-ratelimit-{hdr}-limit")
        remaining = h.get(f"anthropic-ratelimit-{hdr}-remaining")
        reset = h.get(f"anthropic-ratelimit-{hdr}-reset")
        if limit is None and remaining is None:
            continue
        windows[name] = _window(limit, remaining, reset, unit, _parse_rfc3339)
    return windows


def _parse_openai(h: dict) -> dict:
    windows: dict[str, dict] = {}
    specs = [("requests", "requests", "requests"), ("tokens", "tokens", "tokens")]
    for hdr, name, unit in specs:
        limit = h.get(f"x-ratelimit-limit-{hdr}")
        remaining = h.get(f"x-ratelimit-remaining-{hdr}")
        reset = h.get(f"x-ratelimit-reset-{hdr}")
        if limit is None and remaining is None:
            continue
        windows[name] = _window(limit, remaining, reset, unit, _parse_duration)
    return windows


def parse_headers(headers: dict, scheme: str = "auto") -> dict:
    """Return normalized rate-limit windows from response headers."""
    h = _lower(headers)
    if scheme == "auto":
        scheme = detect_scheme(h) or ""
    if scheme == "anthropic":
        return _parse_anthropic(h)
    if scheme == "openai":
        return _parse_openai(h)
    return {}
