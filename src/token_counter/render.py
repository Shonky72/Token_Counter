"""Human-readable rendering of budget statuses.

Two surfaces:
  * ``tooltip_text`` — compact, for the Windows tray hover (kept short; the
    native tooltip is length-limited). One line per provider.
  * ``detail_text`` — full per-model breakdown, for the CLI ``status`` command
    and the tray's details popup.
"""

from __future__ import annotations

from .models import BudgetStatus


def human(n: int) -> str:
    """Compact token count: 1234 -> 1.2K, 1_500_000 -> 1.5M."""
    if n < 1000:
        return str(n)
    if n < 1_000_000:
        return f"{n / 1000:.1f}K".replace(".0K", "K")
    if n < 1_000_000_000:
        return f"{n / 1_000_000:.2f}M".replace(".00M", "M")
    return f"{n / 1_000_000_000:.2f}B"


def overall_percent(statuses: list[BudgetStatus]) -> float | None:
    """Worst-case percent across providers that have a limit (drives icon color)."""
    pcts = [s.percent for s in statuses if s.percent is not None]
    return max(pcts) if pcts else None


def _provider_line(s: BudgetStatus) -> str:
    if s.error:
        return f"{s.provider}: ⚠ {s.error}"
    if s.limit is None:
        return f"{s.provider} ({s.period}): {human(s.used)} used (no limit set)"
    return (
        f"{s.provider} ({s.period}): {human(s.used)}/{human(s.limit)} "
        f"· {human(s.remaining or 0)} left ({s.percent:.0f}%)"
    )


def tooltip_text(statuses: list[BudgetStatus]) -> str:
    if not statuses:
        return "Token Counter — no providers configured"
    return "\n".join(_provider_line(s) for s in statuses)


def detail_text(statuses: list[BudgetStatus]) -> str:
    if not statuses:
        return "No providers configured."
    blocks: list[str] = []
    for s in statuses:
        lines = [_provider_line(s)]
        for m in s.models:
            if m.limit is not None:
                lines.append(
                    f"    {m.model}: {human(m.used)}/{human(m.limit)} "
                    f"({m.percent:.0f}%)"
                )
            else:
                lines.append(f"    {m.model}: {human(m.used)}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)
