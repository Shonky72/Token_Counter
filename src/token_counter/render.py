"""Human-readable rendering of provider statuses.

  * ``tooltip_text`` — compact, for the Windows tray hover (one block per
    provider; the native tooltip is length-limited so keep it tight).
  * ``detail_text`` — full per-gauge breakdown for the CLI ``status`` command
    and the tray's expandable menu.
"""

from __future__ import annotations

from .models import Gauge, ProviderStatus


def human(n: int) -> str:
    if n < 1000:
        return str(n)
    if n < 1_000_000:
        return f"{n / 1000:.1f}K".replace(".0K", "K")
    if n < 1_000_000_000:
        return f"{n / 1_000_000:.1f}M"  # mockup style: 1.7M / 2.0M
    return f"{n / 1_000_000_000:.1f}B"


def overall_percent(statuses: list[ProviderStatus]) -> float | None:
    """Worst-case percent across all providers (drives the icon color)."""
    pcts = [s.worst_percent for s in statuses if s.worst_percent is not None]
    return max(pcts) if pcts else None


def _gauge_line(g: Gauge) -> str:
    if g.limit is None:
        base = f"{g.label}: {human(g.used)} used (no limit)"
    else:
        base = (
            f"{g.label}: {human(g.used)}/{human(g.limit)} "
            f"· {human(g.remaining or 0)} left ({g.percent:.0f}%)"
        )
    reset = g.reset_in_seconds()
    if reset is not None:
        base += f" · resets in {reset}s"
    return base


def _primary_gauge(s: ProviderStatus) -> Gauge | None:
    """The gauge that best summarizes a provider (highest percent, else first)."""
    with_pct = [g for g in s.gauges if g.percent is not None]
    if with_pct:
        return max(with_pct, key=lambda g: g.percent)
    return s.gauges[0] if s.gauges else None


def tooltip_text(statuses: list[ProviderStatus]) -> str:
    if not statuses:
        return "No providers configured"
    lines: list[str] = []
    for s in statuses:
        if s.error:
            lines.append(f"{s.provider}: ⚠ {s.error}")
            continue
        g = _primary_gauge(s)
        if g is None:
            lines.append(f"{s.provider}: no data")
        else:
            lines.append(f"{s.provider} · {_gauge_line(g)}")
    return "\n".join(lines)


def _tray_part(s: ProviderStatus, mode: str) -> str:
    """One provider's hover line. ``mode``: 'amounts' | 'percent'."""
    if s.error:
        return f"{s.provider}: no data"
    g = _primary_gauge(s)
    if g is None:
        return f"{s.provider}: —"
    if mode == "percent" and g.percent is not None:
        return f"{s.provider}: {g.percent:.0f}%"
    if g.limit is not None:
        return f"{s.provider}: {human(g.used)}/{human(g.limit)}"
    return f"{s.provider}: {human(g.used)}"


def tray_title(statuses: list[ProviderStatus], app_name: str = "tokn", limit: int = 120) -> str:
    """Tray-icon hover title showing per-provider amounts (e.g. ``claude: 28K/40K``).

    Hard-capped for the Windows 128-char szTip limit with a tiered fallback so it
    never trips ``Shell_NotifyIcon`` (which made the icon vanish): full amounts →
    percent-only → truncate.
    """
    for mode in ("amounts", "percent"):
        parts = [_tray_part(s, mode) for s in statuses]
        text = app_name + ("\n" + "\n".join(parts) if parts else "")
        if len(text) <= limit:
            return text
    return text[: limit - 1].rstrip() + "…"



def detail_text(statuses: list[ProviderStatus]) -> str:
    if not statuses:
        return "No providers configured."
    blocks: list[str] = []
    for s in statuses:
        header = s.provider
        if s.detail:
            header += f"  ({s.detail})"
        lines = [header]
        if s.error:
            lines.append(f"    ⚠ {s.error}")
        for g in s.gauges:
            lines.append(f"    {_gauge_line(g)}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)
