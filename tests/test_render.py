from datetime import datetime, timedelta, timezone

from token_counter.models import Gauge, ProviderStatus
from token_counter.render import (
    detail_text,
    human,
    overall_percent,
    tooltip_text,
    tray_title,
)


def test_tray_title_capped_under_windows_limit():
    # Three providers with long error messages must NOT exceed the 120-char cap
    # (the real crash was 219 > 128 on Windows szTip).
    long_err = "no rate-limit data yet — make an API call (and forward its headers)"
    statuses = [
        ProviderStatus(provider=name, error=long_err)
        for name in ("claude", "openai", "gemini")
    ]
    title = tray_title(statuses)
    assert len(title) <= 120
    assert title.startswith("tokn")


def test_tray_title_summarizes_percent():
    s = ProviderStatus(provider="claude", gauges=[Gauge("tokens/min", 70, 100)])
    title = tray_title([s])
    assert "claude: 70%" in title
    assert len(title) <= 120


def test_human():
    assert human(500) == "500"
    assert human(1500) == "1.5K"
    assert human(1_000_000) == "1.0M"
    assert human(1_500_000) == "1.5M"


def test_tooltip_shows_used_limit_remaining_percent():
    s = ProviderStatus(
        provider="claude",
        gauges=[Gauge(label="tokens/min", used=28000, limit=40000)],
    )
    text = tooltip_text([s])
    assert "claude" in text
    assert "40K" in text
    assert "70%" in text


def test_tooltip_includes_reset_countdown():
    reset = datetime.now(timezone.utc) + timedelta(seconds=45)
    s = ProviderStatus(
        provider="claude",
        gauges=[Gauge(label="tokens/min", used=10, limit=100, reset_at=reset)],
    )
    assert "resets in" in tooltip_text([s])


def test_tooltip_handles_error():
    s = ProviderStatus(provider="x", error="no rate-limit data yet")
    assert "no rate-limit data yet" in tooltip_text([s])


def test_primary_gauge_picks_highest_percent():
    s = ProviderStatus(
        provider="p",
        gauges=[
            Gauge(label="requests/min", used=1, limit=100),  # 1%
            Gauge(label="tokens/min", used=95, limit=100),   # 95%
        ],
    )
    assert "tokens/min" in tooltip_text([s])


def test_overall_percent_worst_case():
    a = ProviderStatus("a", gauges=[Gauge("t", 10, 100)])
    b = ProviderStatus("b", gauges=[Gauge("t", 90, 100)])
    assert overall_percent([a, b]) == 90


def test_overall_percent_none_without_limits():
    s = ProviderStatus("a", gauges=[Gauge("t", 50, None)])
    assert overall_percent([s]) is None


def test_detail_text_lists_gauges_and_detail():
    s = ProviderStatus(
        provider="claude",
        gauges=[Gauge("tokens/min", 100, 1000), Gauge("requests/min", 2, 50)],
        detail="updated 5s ago",
    )
    text = detail_text([s])
    assert "tokens/min" in text and "requests/min" in text
    assert "updated 5s ago" in text
