"""Pure helpers for usage history: burn-rate, run-out projection, sparklines.

Fed by the ``usage_samples`` the tray records each refresh (see ``ledger.py``).
Everything here is pure (no I/O) so it's trivially testable; the dashboard pulls
the samples and calls these to draw the sparkline + burn/run-out subline.
"""

from __future__ import annotations

Sample = tuple[float, int]  # (epoch_seconds, used)


def burn_rate_per_hour(samples: list[Sample]) -> float:
    """Average tokens/hour across ``samples`` (list of ``(ts, used)``).

    Sums only the *rises* in ``used`` (a drop means the rate-limit window reset,
    not negative usage) and divides by the total elapsed time. Returns 0.0 when
    there isn't enough signal.
    """
    pts = sorted((t, u) for t, u in samples if u is not None)
    if len(pts) < 2:
        return 0.0
    span = pts[-1][0] - pts[0][0]
    if span <= 0:
        return 0.0
    gained = 0
    for (t0, u0), (t1, u1) in zip(pts, pts[1:]):
        if u1 > u0:
            gained += u1 - u0
    return gained / (span / 3600.0)


def cumulative_series(samples: list[Sample]) -> list[float]:
    """Running total of *consumed* tokens (sum of positive deltas) across samples.

    Rate-limit ``used`` resets to ~0 every window, so the raw series is a sawtooth;
    this turns it into a monotonic 24h trend suitable for a sparkline.
    """
    pts = sorted((t, u) for t, u in samples if u is not None)
    out: list[float] = []
    total = 0.0
    prev = None
    for _t, u in pts:
        if prev is not None and u > prev:
            total += u - prev
        prev = u
        out.append(total)
    return out


def runout_seconds(remaining: int | None, rate_per_hour: float) -> float | None:
    """Seconds until ``remaining`` tokens are exhausted at ``rate_per_hour``."""
    if remaining is None or remaining <= 0 or rate_per_hour <= 0:
        return None
    return remaining / rate_per_hour * 3600.0


def runout_text(remaining: int | None, rate_per_hour: float) -> str:
    """Human run-out estimate, e.g. "runs out in ~3h" / "~2.1d", else ""."""
    secs = runout_seconds(remaining, rate_per_hour)
    if secs is None:
        return ""
    if secs < 3600:
        return f"runs out in ~{max(1, round(secs / 60))}m"
    if secs < 48 * 3600:
        return f"runs out in ~{round(secs / 3600)}h"
    return f"runs out in ~{secs / 86400.0:.1f}d"


def human_rate(rate_per_hour: float) -> str:
    """Format a tokens/hour rate compactly, e.g. "12K/h"."""
    from .render import human

    if rate_per_hour <= 0:
        return ""
    return f"{human(round(rate_per_hour))}/h"


def spark_points(values: list[float], w: float, h: float, pad: float = 1.0) -> list[tuple[float, float]]:
    """Map ``values`` to polyline (x, y) coords in a ``w``×``h`` box.

    Higher values sit higher (smaller y). A flat series renders as a mid-line.
    Returns [] for fewer than 2 points.
    """
    vals = [v for v in values if v is not None]
    if len(vals) < 2:
        return []
    lo, hi = min(vals), max(vals)
    span = hi - lo
    inner_w = max(1.0, w - 2 * pad)
    inner_h = max(1.0, h - 2 * pad)
    n = len(vals)
    pts: list[tuple[float, float]] = []
    for i, v in enumerate(vals):
        x = pad + inner_w * (i / (n - 1))
        frac = 0.5 if span == 0 else (v - lo) / span
        y = pad + inner_h * (1 - frac)
        pts.append((x, y))
    return pts
