"""Serialize the engine's view-model into the web UI's data shape.

The bundled Material 3 design (``assets/web``) is data-driven: every screen reads
``PARTS.DASH_DATA`` (a list of ``{key, tokens, pct, resets, inp, out, msgs,
rate}``) and ``PARTS.PROVIDERS[theme][key]`` (the per-provider tonal colours).
This module turns ``ProviderStatus`` + ``AppConfig`` into exactly that JSON, so
the same screens the designer mocked render live data unchanged.

Kept pure (no pywebview, no display) so it's fully unit-tested headless.
"""

from __future__ import annotations

import colorsys
from typing import Any

from .config import AppConfig, ProviderConfig
from .models import ProviderStatus
from .render import human
from .viewmodel import _group_cards, build_card

# The three colour sets the designer hand-tuned in parts.js (per theme, per
# service). We reuse them verbatim so the Big-3 match the mock pixel-for-pixel;
# every other service derives a tonal set from its brand accent (below).
_DESIGN_PROVIDERS: dict[str, dict[str, dict[str, str]]] = {
    "dark": {
        "claude": {"glyph": "sunburst", "gauge": "#ffb59b", "track": "#5a3f33",
                   "container": "#4d2a1b", "onContainer": "#ffdbcf"},
        "openai": {"glyph": "ring", "gauge": "#54dbb6", "track": "#234a40",
                   "container": "#00382c", "onContainer": "#74f8d8"},
        "gemini": {"glyph": "spark", "gauge": "#adc6ff", "track": "#3a4763",
                   "container": "#243665", "onContainer": "#dae2ff"},
    },
    "light": {
        "claude": {"glyph": "sunburst", "gauge": "#9b4521", "track": "#f4d6c8",
                   "container": "#ffdbcf", "onContainer": "#370e00"},
        "openai": {"glyph": "ring", "gauge": "#006a52", "track": "#bdeada",
                   "container": "#76f6d6", "onContainer": "#002019"},
        "gemini": {"glyph": "spark", "gauge": "#3a5ba8", "track": "#cdd7f5",
                   "container": "#dae2ff", "onContainer": "#001949"},
    },
}

# Simple geometric mark per service (the design uses marks, not real logos).
_GLYPHS = {
    "claude": "sunburst", "anthropic": "sunburst",
    "openai": "ring", "chatgpt": "ring", "gpt": "ring",
    "gemini": "spark", "google": "spark",
    "grok": "spark", "deepseek": "ring", "mistral": "sunburst",
    "perplexity": "ring", "openrouter": "spark",
}


def _hex_to_hls(hex_color: str) -> tuple[float, float, float]:
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = (int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    return colorsys.rgb_to_hls(r, g, b)


def _hls_to_hex(h: float, l: float, s: float) -> str:
    r, g, b = colorsys.hls_to_rgb(h % 1.0, max(0.0, min(1.0, l)), max(0.0, min(1.0, s)))
    return "#{:02x}{:02x}{:02x}".format(round(r * 255), round(g * 255), round(b * 255))


def _derive_tones(accent: str, theme: str) -> dict[str, str]:
    """A Material-You-ish tonal set from a single brand accent.

    Not true HCT, but produces a coherent gauge/track/container/onContainer family
    that reads correctly in both themes for the providers the designer didn't
    hand-tune.
    """
    h, _l, s = _hex_to_hls(accent)
    sat = max(0.30, min(0.85, s))
    if theme == "light":
        return {
            "gauge": _hls_to_hex(h, 0.38, sat),
            "track": _hls_to_hex(h, 0.86, sat * 0.55),
            "container": _hls_to_hex(h, 0.92, sat * 0.5),
            "onContainer": _hls_to_hex(h, 0.18, sat),
        }
    return {
        "gauge": _hls_to_hex(h, 0.74, sat),
        "track": _hls_to_hex(h, 0.30, sat * 0.5),
        "container": _hls_to_hex(h, 0.22, sat * 0.6),
        "onContainer": _hls_to_hex(h, 0.86, sat),
    }


def _provider_colors(service: str, accent: str, name: str, theme: str) -> dict[str, str]:
    base = _DESIGN_PROVIDERS.get(theme, {}).get(service)
    if base is not None:
        out = dict(base)
    else:
        out = _derive_tones(accent, theme)
        out["glyph"] = _GLYPHS.get(service, "sunburst")
    out["name"] = name
    return out


def _reset_short(reset_text: str | None) -> str:
    """"Resets 41s" -> "41s"; None -> ""."""
    if not reset_text:
        return ""
    prefix = "Resets "
    return reset_text[len(prefix):] if reset_text.startswith(prefix) else reset_text


def _io_pair(status: ProviderStatus, kind: str) -> str:
    """"used / limit" for the input/output token gauge, or "" if absent."""
    for g in status.gauges:
        if kind in g.label.lower():
            limit = human(g.limit) if g.limit is not None else "∞"
            return f"{human(g.used)} / {limit}"
    return ""


def card_dict(status: ProviderStatus, cfg: ProviderConfig | None, *,
              basis: str, theme: str, extra: dict[str, Any] | None = None) -> tuple[dict, dict]:
    """Return ``(dash_item, provider_colors)`` for one provider."""
    # metric="amount" so the split-flap always shows the token amount; the ring
    # shows percent separately (the design renders both).
    card = build_card(status, cfg, "amount", basis)
    extra = extra or {}
    key = card.provider or card.service
    item = {
        "key": key,
        "service": card.service,
        "tokens": card.error or card.primary_text,
        "pct": card.percent if card.percent is not None else 0,
        "resets": _reset_short(card.reset_text),
        "inp": _io_pair(status, "input"),
        "out": _io_pair(status, "output"),
        "msgs": card.subtitle or "tracked usage",
        "rate": extra.get("rate", ""),
        "cost": extra.get("cost", ""),
        "spark": extra.get("spark", []),
        "usage_url": card.usage_url,
        "error": card.error,
    }
    colors = _provider_colors(card.service, card.accent, card.title, theme)
    return item, colors


def build_state(config: AppConfig, statuses: list[ProviderStatus], *,
                theme: str = "dark", extras: dict[str, dict] | None = None,
                version: str = "") -> dict:
    """The full JSON state the web UI consumes (``json.dumps``-able)."""
    by_name = {c.name: c for c in config.providers}
    basis = config.token_basis
    extras = extras or {}

    # Build per-status cards, then keep instances of the same service adjacent
    # (mirrors viewmodel._group_cards, which works on the CardVM order).
    cards = [build_card(s, by_name.get(s.provider), "amount", basis) for s in statuses]
    order = [c.provider or c.service for c in _group_cards(list(cards))]
    by_key = {}
    for s in statuses:
        cfg = by_name.get(s.provider)
        item, colors = card_dict(s, cfg, basis=basis, theme=theme,
                                  extra=extras.get(s.provider))
        by_key[item["key"]] = (item, colors)

    dash, providers = [], {}
    for key in order:
        if key in by_key:
            item, colors = by_key.pop(key)
            dash.append(item)
            providers[key] = colors
    for item, colors in by_key.values():  # any not covered by the order
        dash.append(item)
        providers[item["key"]] = colors

    n = len(dash)
    return {
        "theme": theme,
        "providers": {theme: providers},
        "cards": dash,
        "meta": {
            "version": version,
            "refresh_seconds": config.refresh_seconds,
            "services_line": f"{n} service{'' if n == 1 else 's'} · "
                             f"live within {config.refresh_seconds}s",
            "metric": config.display_metric,
            "basis": basis,
            "show_cost": config.show_cost,
            "show_sparkline": config.show_sparkline,
            "alert_threshold": config.alert_threshold,
        },
    }
