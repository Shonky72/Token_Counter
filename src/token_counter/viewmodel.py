"""Presentation model for the dashboard and compact views.

Turns ``ProviderStatus`` + per-provider display options into the exact strings
and colors the windows render — kept pure so it's fully unit-tested without a
display. Mirrors the mockup: ring/bar gauge, "1.7M / 2.0M tokens" or
"12 / 45 messages", input/output sub-lines, "Resets in 14m".
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .config import ProviderConfig
from .models import Gauge, ProviderStatus
from .render import human

# Brand-ish accent colors, matched to the mockup, picked by name keyword.
_ACCENTS = {
    "openai": "#10a37f",
    "chatgpt": "#10a37f",
    "gpt": "#10a37f",
    "claude": "#d97757",
    "anthropic": "#d97757",
    "gemini": "#4285f4",
    "google": "#4285f4",
}
_DEFAULT_ACCENT = "#5a78c8"

# rate-limit "requests" reads as "messages" in a chat context (see mockup).
_NOUN = {"requests": "messages", "tokens": "tokens"}


@dataclass
class CardVM:
    title: str
    accent: str
    style: str  # "ring" | "bar"
    percent: int | None
    primary_text: str
    sub_lines: list[str] = field(default_factory=list)
    reset_text: str | None = None
    detail: str | None = None
    error: str | None = None
    provider: str = ""          # raw provider name (for logo lookup)
    scheme: str | None = None   # e.g. "anthropic" (helps pick the logo)


@dataclass
class CompactVM:
    title: str
    accent: str
    percent: int | None
    primary_text: str
    provider: str = ""
    scheme: str | None = None


def format_duration(seconds: int | None) -> str | None:
    """45 -> '45s', 840 -> '14m', 3900 -> '1h 05m'."""
    if seconds is None:
        return None
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m"
    hours, mins = divmod(seconds // 60, 60)
    return f"{hours}h {mins:02d}m"


def _noun(unit: str) -> str:
    return _NOUN.get(unit, unit)


def format_count(used: int, limit: int | None, unit: str) -> str:
    noun = _noun(unit)
    if unit == "tokens":
        used_s, limit_s = human(used), (human(limit) if limit is not None else "∞")
    else:  # messages/requests: show raw integers
        used_s, limit_s = str(used), (str(limit) if limit is not None else "∞")
    return f"{used_s} / {limit_s} {noun}"


def accent_for(name: str, override: str | None = None) -> str:
    if override:
        return override
    low = name.lower()
    for key, color in _ACCENTS.items():
        if key in low:
            return color
    return _DEFAULT_ACCENT


# The aggregate windows that should headline a card; the input/output token
# windows are shown as sub-lines beneath, not as the primary.
_MAIN_LABELS = ("tokens/min", "requests/min")


def _primary_gauge(status: ProviderStatus, preferred: str | None) -> Gauge | None:
    if not status.gauges:
        return None
    if preferred:
        for g in status.gauges:
            if preferred in g.label:
                return g
    # Prefer the aggregate tokens/requests window over input/output breakdowns.
    for label in _MAIN_LABELS:
        for g in status.gauges:
            if g.label == label:
                return g
    with_pct = [g for g in status.gauges if g.percent is not None]
    if with_pct:
        return max(with_pct, key=lambda g: g.percent)
    return status.gauges[0]


def build_card(status: ProviderStatus, cfg: ProviderConfig | None = None) -> CardVM:
    style = (cfg.option("display", "ring") if cfg else "ring")
    color_override = cfg.option("color") if cfg else None
    preferred = cfg.option("primary") if cfg else None
    accent = accent_for(status.provider, color_override)
    title = (cfg.option("display_name") if cfg else None) or status.provider
    scheme = cfg.option("scheme") if cfg else None

    if status.error:
        return CardVM(
            title=title, accent=accent, style=style, percent=None,
            primary_text="—", error=status.error, detail=status.detail,
            provider=status.provider, scheme=scheme,
        )

    primary = _primary_gauge(status, preferred)
    if primary is None:
        return CardVM(title=title, accent=accent, style=style, percent=None,
                      primary_text="no data", detail=status.detail,
                      provider=status.provider, scheme=scheme)

    percent = round(primary.percent) if primary.percent is not None else None
    primary_text = format_count(primary.used, primary.limit, primary.unit)

    sub_lines = []
    for g in status.gauges:
        if g is primary:
            continue
        sub_lines.append(f"{g.label}: {format_count(g.used, g.limit, g.unit)}")

    reset_secs = primary.reset_in_seconds()
    reset_text = (
        f"Resets in {format_duration(reset_secs)}" if reset_secs is not None else None
    )

    return CardVM(
        title=title, accent=accent, style=style, percent=percent,
        primary_text=primary_text, sub_lines=sub_lines,
        reset_text=reset_text, detail=status.detail,
        provider=status.provider, scheme=scheme,
    )


def build_cards(
    statuses: list[ProviderStatus], configs: list[ProviderConfig] | None = None
) -> list[CardVM]:
    by_name = {c.name: c for c in (configs or [])}
    return [build_card(s, by_name.get(s.provider)) for s in statuses]


def build_compact(
    statuses: list[ProviderStatus], configs: list[ProviderConfig] | None = None
) -> list[CompactVM]:
    cards = build_cards(statuses, configs)
    return [
        CompactVM(title=c.title, accent=c.accent, percent=c.percent,
                  primary_text=(c.error or c.primary_text),
                  provider=c.provider, scheme=c.scheme)
        for c in cards
    ]
