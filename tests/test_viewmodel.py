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


def test_reel_frames_zero_target_still_spins():
    # Even at 0 the reel must visibly spin (so the reveal is never a no-op),
    # then land exactly on 0.
    frames = reel_frames(0, spin=14, settle=12, seed=1)
    assert frames[-1] == 0
    assert len(frames) == 26
    assert max(frames) > 0  # it rolled through non-zero values


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


def test_display_strings_used_and_remaining():
    from token_counter.viewmodel import display_strings

    g = Gauge("tokens/min", used=847_000, limit=2_000_000, unit="tokens")
    assert display_strings(g, "amount", "used") == ("847K / 2.0M tokens", "42%")
    assert display_strings(g, "percent", "used") == ("42%", "847K / 2.0M tokens")
    assert display_strings(g, "amount", "remaining") == ("1.2M left", "58%")
    assert display_strings(g, "percent", "remaining") == ("58%", "1.2M left")


def test_display_strings_no_limit():
    from token_counter.viewmodel import display_strings

    g = Gauge("tokens/min", used=500, limit=None, unit="tokens")
    primary, opposite = display_strings(g, "amount", "used")
    assert primary == "500 / ∞ tokens" and opposite == "—"


def test_build_card_subtitle_and_unit_label():
    status = ProviderStatus(
        provider="claude",
        gauges=[
            Gauge("tokens/min", used=28_000, limit=40_000, unit="tokens"),
            Gauge("requests/min", used=12, limit=45, unit="requests"),
            Gauge("input tokens/min", used=18_000, limit=40_000, unit="tokens"),
            Gauge("output tokens/min", used=10_000, limit=40_000, unit="tokens"),
        ],
    )
    vm = build_card(status)
    assert vm.subtitle == "12 / 45 msgs"
    assert vm.unit_label == "TOKENS / MIN"
    assert "↑ 18K" in vm.io_text and "↓ 10K" in vm.io_text


def test_build_card_subtitle_falls_back():
    # No requests window, no detail → "tracked usage".
    status = ProviderStatus(provider="gemini",
                            gauges=[Gauge("tokens/day", used=0, limit=2_000_000, unit="tokens")])
    assert build_card(status).subtitle == "tracked usage"
    # detail wins when present
    status2 = ProviderStatus(provider="claude", detail="tier: build",
                             gauges=[Gauge("tokens/min", used=1, limit=100)])
    assert build_card(status2).subtitle == "tier: build"


def test_build_card_hover_is_opposite():
    status = ProviderStatus(
        provider="claude",
        gauges=[Gauge("tokens/min", used=847_000, limit=2_000_000, unit="tokens")],
    )
    vm = build_card(status)  # defaults: amount + used
    assert vm.primary_text == "847K / 2.0M tokens"
    assert vm.hover_text == "42%"
    vm2 = build_card(status, metric="percent", basis="remaining")
    assert vm2.primary_text == "58%" and vm2.hover_text == "1.2M left"
    assert vm2.percent == 58


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
    assert vm.reset_text == "Resets 14m"


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


def test_build_cards_groups_instances_and_uses_service_accent():
    statuses = [
        ProviderStatus(provider="claude", gauges=[Gauge("requests/min", 1, 100)]),
        ProviderStatus(provider="gemini", gauges=[Gauge("tokens/min", 1, 100)]),
        ProviderStatus(provider="claude-2", gauges=[Gauge("requests/min", 1, 100)]),
    ]
    cfg = parse_config({"providers": [
        {"name": "claude", "type": "rate_limit", "service": "claude",
         "display_name": "Claude — Work"},
        {"name": "gemini", "type": "rate_limit", "service": "gemini"},
        {"name": "claude-2", "type": "rate_limit", "service": "claude",
         "display_name": "Claude — Home"},
    ]})
    cards = build_cards(statuses, cfg.providers)
    # The two Claude instances are grouped together, ahead of gemini.
    assert [c.provider for c in cards] == ["claude", "claude-2", "gemini"]
    # Accent + service id resolve from the catalog service, not the instance name.
    assert cards[0].service == "claude" and cards[0].accent == "#d97757"
    assert cards[1].service == "claude" and cards[1].accent == "#d97757"
