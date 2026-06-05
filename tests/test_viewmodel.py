from datetime import datetime, timedelta, timezone

from token_counter.config import parse_config
from token_counter.models import Gauge, ProviderStatus
from token_counter.viewmodel import (
    accent_for,
    build_card,
    build_cards,
    build_compact,
    ease_out_frames,
    format_count,
    format_duration,
    reel_frames,
)


def test_ease_out_frames_ends_on_target():
    frames = ease_out_frames(0, 1000, steps=18)
    assert frames[-1] == 1000
    assert len(frames) == 18
    assert frames == sorted(frames)  # monotonic up


def test_ease_out_frames_noop_when_equal():
    assert ease_out_frames(500, 500) == [500]


def test_reel_frames_ends_on_target():
    frames = reel_frames(40000, spin=14, settle=12, seed=1)
    assert frames[-1] == 40000
    assert len(frames) == 26
    # The spin phase should jump around (not be monotonic), unlike a plain count-up.
    assert frames[:14] != sorted(frames[:14])


def test_reel_frames_zero_target():
    assert reel_frames(0)[-1] == 0


def test_format_duration():
    assert format_duration(45) == "45s"
    assert format_duration(840) == "14m"
    assert format_duration(3900) == "1h 05m"
    assert format_duration(None) is None


def test_format_count_tokens_vs_messages():
    assert format_count(1_700_000, 2_000_000, "tokens") == "1.7M / 2.0M tokens"
    assert format_count(12, 45, "requests") == "12 / 45 messages"


def test_accent_for_keyword_and_override():
    assert accent_for("ChatGPT") == "#10a37f"
    assert accent_for("claude") == "#d97757"
    assert accent_for("gemini") == "#4285f4"
    assert accent_for("mystery") == "#5a78c8"
    assert accent_for("claude", "#000000") == "#000000"


def _cfg(opts):
    raw = {"providers": [dict({"name": "claude", "type": "rate_limit"}, **opts)]}
    return parse_config(raw).providers[0]


def test_build_card_ring_with_sublines_and_reset():
    reset = datetime.now(timezone.utc) + timedelta(seconds=14 * 60 + 5)
    status = ProviderStatus(
        provider="claude",
        gauges=[
            Gauge("tokens/min", used=1_700_000, limit=2_000_000, unit="tokens", reset_at=reset),
            Gauge("input tokens/min", used=900_000, limit=1_000_000, unit="tokens"),
        ],
        detail="updated 2s ago",
    )
    vm = build_card(status, _cfg({"display": "ring", "display_name": "Claude"}))
    assert vm.title == "Claude"
    assert vm.style == "ring"
    assert vm.percent == 85
    assert vm.primary_text == "1.7M / 2.0M tokens"
    assert any("input tokens/min" in s for s in vm.sub_lines)
    assert vm.reset_text == "Resets in 14m"


def test_build_card_respects_preferred_primary():
    status = ProviderStatus(
        provider="claude",
        gauges=[
            Gauge("tokens/min", used=10, limit=100, unit="tokens"),       # 10%
            Gauge("requests/min", used=12, limit=45, unit="requests"),    # ~27%
        ],
    )
    vm = build_card(status, _cfg({"primary": "requests"}))
    assert vm.primary_text == "12 / 45 messages"


def test_build_card_error():
    vm = build_card(ProviderStatus(provider="x", error="no data yet"))
    assert vm.error == "no data yet"
    assert vm.percent is None


def test_build_compact_uses_titles_and_accents():
    statuses = [ProviderStatus(provider="openai", gauges=[Gauge("tokens/min", 1, 100)])]
    cfg = parse_config({"providers": [{"name": "openai", "type": "rate_limit",
                                       "display_name": "ChatGPT"}]})
    [vm] = build_compact(statuses, cfg.providers)
    assert vm.title == "ChatGPT"
    assert vm.accent == "#10a37f"
