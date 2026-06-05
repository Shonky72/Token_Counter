import time
from datetime import datetime, timezone

from token_counter.ratelimit import detect_scheme, parse_headers


def test_detect_scheme():
    assert detect_scheme({"anthropic-ratelimit-tokens-limit": "1"}) == "anthropic"
    assert detect_scheme({"x-ratelimit-limit-tokens": "1"}) == "openai"
    assert detect_scheme({"content-type": "application/json"}) is None


def test_parse_anthropic_headers():
    reset = "2026-06-05T00:00:30Z"
    windows = parse_headers(
        {
            "anthropic-ratelimit-tokens-limit": "40000",
            "anthropic-ratelimit-tokens-remaining": "12000",
            "anthropic-ratelimit-tokens-reset": reset,
            "anthropic-ratelimit-requests-limit": "50",
            "anthropic-ratelimit-requests-remaining": "49",
            "anthropic-ratelimit-requests-reset": reset,
        }
    )
    assert windows["tokens"]["limit"] == 40000
    assert windows["tokens"]["remaining"] == 12000
    expected = datetime(2026, 6, 5, 0, 0, 30, tzinfo=timezone.utc).timestamp()
    assert abs(windows["tokens"]["reset_at"] - expected) < 1
    assert windows["requests"]["unit"] == "requests"


def test_parse_openai_headers_duration_reset():
    now = time.time()
    windows = parse_headers(
        {
            "x-ratelimit-limit-tokens": "90000",
            "x-ratelimit-remaining-tokens": "89000",
            "x-ratelimit-reset-tokens": "6m0s",
        }
    )
    assert windows["tokens"]["limit"] == 90000
    # 6 minutes from now-ish
    assert windows["tokens"]["reset_at"] >= now + 350


def test_parse_openai_bare_seconds_reset():
    now = time.time()
    windows = parse_headers(
        {
            "x-ratelimit-limit-requests": "100",
            "x-ratelimit-remaining-requests": "99",
            "x-ratelimit-reset-requests": "30",
        }
    )
    assert abs(windows["requests"]["reset_at"] - (now + 30)) < 2


def test_case_insensitive_headers():
    windows = parse_headers({"X-RateLimit-Limit-Tokens": "5", "X-RateLimit-Remaining-Tokens": "4"})
    assert windows["tokens"]["limit"] == 5


def test_unknown_headers_yield_nothing():
    assert parse_headers({"server": "nginx"}) == {}
