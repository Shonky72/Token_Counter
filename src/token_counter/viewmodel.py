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
    hover_text: str = ""        # the "other" metric, shown on hover
    sub_lines: list[str] = field(default_factory=list)
    reset_text: str | None = None
    detail: str | None = None
    error: str | None = None
    provider: str = ""          # unique instance name
    service: str = ""           # catalog service id (for logo/accent)
    scheme: str | None = None   # e.g. "anthropic" (helps pick the logo)
    usage_url: str | None = None  # billing/usage console (click-through)
    used: int = 0               # primary gauge values (for the count-up animation)
    limit: int | None = None
    unit: str = "tokens"


def ease_out_frames(start: int, target: int, steps: int = 18) -> list[int]:
    """Ease-out integer frames from ``start`` to ``target`` (last == target)."""
    if steps < 1 or start == target:
        return [target]
    frames = []
    span = target - start
    for i in range(1, steps + 1):
        t = i / steps
        eased = 1 - (1 - t) ** 3  # cubic ease-out
        frames.append(round(start + span * eased))
    frames[-1] = target
    return frames


def reel_frames(target: int, spin: int = 14, settle: int = 12, seed: int | None = None) -> list[int]:
    """Slot-machine reel: ``spin`` fast random values, then ease into ``target``.

    Always includes a spin phase — even when ``target == 0`` (so the reel is
    visible on every reveal). Deterministic length (``spin + settle``); the last
    frame is exactly ``target``. Pass ``seed`` for reproducible tests.
    """
    import random

    rng = random.Random(seed)
    hi = max(target, 100)          # roll through a believable range even at 0
    lo = max(0, target // 3)
    frames = [rng.randint(lo, hi) for _ in range(spin)]
    frames += ease_out_frames(frames[-1] if frames else hi, target, settle)
    frames[-1] = target
    return frames


@dataclass
class CompactVM:
    title: str
    accent: str
    percent: int | None
    primary_text: str
    hover_text: str = ""
    provider: str = ""
    service: str = ""
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


def basis_percent(gauge: Gauge, basis: str = "used") -> float | None:
    """The percent to show/draw for ``basis`` ("used" → used%, "remaining" → left%)."""
    pct = gauge.percent
    if pct is None:
        return None
    if basis == "remaining" and gauge.limit is not None:
        return max(0.0, 100.0 - pct)
    return pct


def _amount_str(gauge: Gauge, basis: str) -> str:
    if basis == "remaining" and gauge.limit is not None:
        rem = gauge.remaining or 0
        return f"{human(rem)} left" if gauge.unit == "tokens" else f"{rem} left"
    return format_count(gauge.used, gauge.limit, gauge.unit)


def display_strings(gauge: Gauge, metric: str = "amount", basis: str = "used") -> tuple[str, str]:
    """Return (primary, opposite) display strings for a gauge.

    ``metric`` chooses the headline ("amount" or "percent"); the other one is the
    hover value. ``basis`` chooses used vs remaining for both.
    """
    shown = basis_percent(gauge, basis)
    pct_str = f"{round(shown)}%" if shown is not None else "—"
    amount = _amount_str(gauge, basis)
    if metric == "percent":
        return pct_str, amount
    return amount, pct_str


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


def build_card(status: ProviderStatus, cfg: ProviderConfig | None = None,
               metric: str = "amount", basis: str = "used") -> CardVM:
    style = (cfg.option("display", "ring") if cfg else "ring")
    color_override = cfg.option("color") if cfg else None
    preferred = cfg.option("primary") if cfg else None
    service = (cfg.option("service") if cfg else None) or status.provider
    accent = accent_for(service, color_override)
    title = (cfg.option("display_name") if cfg else None) or status.provider
    scheme = cfg.option("scheme") if cfg else None
    usage_url = cfg.option("usage_url") if cfg else None

    if status.error:
        return CardVM(
            title=title, accent=accent, style=style, percent=None,
            primary_text="—", error=status.error, detail=status.detail,
            provider=status.provider, service=service, scheme=scheme,
            usage_url=usage_url,
        )

    primary = _primary_gauge(status, preferred)
    if primary is None:
        return CardVM(title=title, accent=accent, style=style, percent=None,
                      primary_text="no data", detail=status.detail,
                      provider=status.provider, service=service, scheme=scheme,
                      usage_url=usage_url)

    shown_pct = basis_percent(primary, basis)
    percent = round(shown_pct) if shown_pct is not None else None
    primary_text, hover_text = display_strings(primary, metric, basis)

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
        primary_text=primary_text, hover_text=hover_text, sub_lines=sub_lines,
        reset_text=reset_text, detail=status.detail,
        provider=status.provider, service=service, scheme=scheme,
        usage_url=usage_url,
        used=primary.used, limit=primary.limit, unit=primary.unit,
    )


def build_cards(
    statuses: list[ProviderStatus], configs: list[ProviderConfig] | None = None,
    metric: str = "amount", basis: str = "used",
) -> list[CardVM]:
    by_name = {c.name: c for c in (configs or [])}
    cards = [build_card(s, by_name.get(s.provider), metric, basis) for s in statuses]
    return _group_cards(cards)


def _group_cards(cards: list[CardVM]) -> list[CardVM]:
    """Keep instances of the same service adjacent (first-appearance order)."""
    order: list[str] = []
    groups: dict[str, list[CardVM]] = {}
    for c in cards:
        key = c.service or c.provider
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(c)
    out: list[CardVM] = []
    for key in order:
        out.extend(groups[key])
    return out


def build_compact(
    statuses: list[ProviderStatus], configs: list[ProviderConfig] | None = None,
    metric: str = "amount", basis: str = "used",
) -> list[CompactVM]:
    cards = build_cards(statuses, configs, metric, basis)
    return [
        CompactVM(title=c.title, accent=c.accent, percent=c.percent,
                  primary_text=(c.error or c.primary_text), hover_text=c.hover_text,
                  provider=c.provider, service=c.service, scheme=c.scheme)
        for c in cards
    ]
