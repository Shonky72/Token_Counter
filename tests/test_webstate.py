"""Tests for the web UI data bridge (headless — no pywebview/display)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from token_counter import webstate
from token_counter.config import parse_config
from token_counter.models import Gauge, ProviderStatus


def _config(providers):
    return parse_config({"providers": providers})


def _three():
    reset = datetime.now(timezone.utc) + timedelta(seconds=41)
    statuses = [
        ProviderStatus(provider="claude", gauges=[
            Gauge("tokens/min", 28_000, 40_000, reset_at=reset),
            Gauge("requests/min", 12, 45, unit="requests"),
            Gauge("input tokens/min", 18_000, 30_000),
            Gauge("output tokens/min", 10_000, 20_000),
        ]),
        ProviderStatus(provider="openai", gauges=[Gauge("tokens/min", 1_700_000, 2_000_000)]),
        ProviderStatus(provider="gemini", gauges=[Gauge("tokens/day", 540_000, 1_000_000)]),
    ]
    config = _config([
        {"name": "claude", "type": "rate_limit", "service": "claude"},
        {"name": "openai", "type": "rate_limit", "service": "openai",
         "display_name": "ChatGPT"},
        {"name": "gemini", "type": "rate_limit", "service": "gemini"},
    ])
    return config, statuses


def test_state_is_json_serializable_with_design_keys():
    config, statuses = _three()
    state = webstate.build_state(config, statuses, theme="dark", version="0.1.0")
    json.dumps(state)  # must not raise

    assert state["theme"] == "dark"
    assert {"theme", "providers", "cards", "meta"} <= set(state)
    assert len(state["cards"]) == 3
    for card in state["cards"]:
        assert {"key", "tokens", "pct", "resets", "inp", "out", "msgs", "rate"} <= set(card)


def test_card_values_match_view_model():
    config, statuses = _three()
    cards = {c["key"]: c for c in webstate.build_state(config, statuses)["cards"]}

    claude = cards["claude"]
    assert claude["tokens"] == "28K / 40K tokens"
    assert claude["pct"] == 70
    assert claude["resets"] in {"41s", "40s"}  # "Resets 41s" -> "41s" (clock ticks)
    assert claude["inp"] == "18K / 30K"
    assert claude["out"] == "10K / 20K"
    assert claude["msgs"] == "12 / 45 msgs"

    assert cards["openai"]["pct"] == 85
    assert cards["gemini"]["inp"] == ""        # no input/output gauge


def test_providers_use_design_colors_for_big_three():
    config, statuses = _three()
    state = webstate.build_state(config, statuses, theme="dark")
    prov = state["providers"]["dark"]
    assert prov["claude"]["gauge"] == "#ffb59b"      # hand-tuned design value
    assert prov["openai"]["name"] == "ChatGPT"       # display_name carried through
    assert prov["gemini"]["glyph"] == "spark"


def test_unknown_provider_derives_a_tonal_set():
    config = _config([{"name": "grok", "type": "rate_limit", "service": "grok"}])
    statuses = [ProviderStatus(provider="grok", gauges=[Gauge("tokens/min", 5, 10)])]
    prov = webstate.build_state(config, statuses, theme="dark")["providers"]["dark"]
    colors = prov["grok"]
    assert set(colors) >= {"gauge", "track", "container", "onContainer", "glyph", "name"}
    for key in ("gauge", "track", "container", "onContainer"):
        assert colors[key].startswith("#") and len(colors[key]) == 7


def test_meta_and_grouping():
    config, statuses = _three()
    # add a second Claude instance — must group adjacent to the first.
    statuses.append(ProviderStatus(provider="claude-2", gauges=[Gauge("tokens/min", 1, 100)]))
    config = _config([
        {"name": "claude", "type": "rate_limit", "service": "claude"},
        {"name": "openai", "type": "rate_limit", "service": "openai"},
        {"name": "gemini", "type": "rate_limit", "service": "gemini"},
        {"name": "claude-2", "type": "rate_limit", "service": "claude"},
    ])
    state = webstate.build_state(config, statuses)
    keys = [c["key"] for c in state["cards"]]
    assert keys.index("claude-2") == keys.index("claude") + 1
    assert state["meta"]["services_line"].startswith("4 services · live within")


def test_error_card_carries_message():
    config = _config([{"name": "x", "type": "rate_limit", "service": "x"}])
    statuses = [ProviderStatus(provider="x", error="no rate-limit data yet")]
    card = webstate.build_state(config, statuses)["cards"][0]
    assert card["error"] == "no rate-limit data yet"
    assert card["tokens"] == "no rate-limit data yet"
    assert card["pct"] == 0


def test_light_theme_derives_light_tones():
    config = _config([{"name": "grok", "type": "rate_limit", "service": "grok"}])
    statuses = [ProviderStatus(provider="grok", gauges=[Gauge("tokens/min", 5, 10)])]
    state = webstate.build_state(config, statuses, theme="light")
    assert "light" in state["providers"]
    json.dumps(state)
