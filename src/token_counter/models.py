"""Core data structures shared across the app.

Plain dataclasses with no I/O — trivial to construct in tests and to pass
between the ledger, providers, engine, render and tray layers.

The central render type is ``Gauge``: one bar of "used / limit (remaining)".
Both provider-enforced rate-limit windows and manual ledger budgets reduce to a
list of gauges, so every surface renders them the same way.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class ModelUsage:
    """Token usage for a single model within some time window (ledger mode)."""

    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0

    @property
    def total(self) -> int:
        return (
            self.input_tokens
            + self.output_tokens
            + self.cache_read_tokens
            + self.cache_creation_tokens
        )

    def merged_with(self, other: "ModelUsage") -> "ModelUsage":
        if other.model != self.model:
            raise ValueError(f"cannot merge {self.model!r} with {other.model!r}")
        return ModelUsage(
            model=self.model,
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            cache_read_tokens=self.cache_read_tokens + other.cache_read_tokens,
            cache_creation_tokens=self.cache_creation_tokens + other.cache_creation_tokens,
        )


@dataclass
class Gauge:
    """One "used / limit (remaining)" bar.

    ``unit`` is ``tokens`` or ``requests``. ``reset_at`` is when the window
    refills (rate-limit windows) — used to show a countdown and to roll the
    bar back to full once it has passed.
    """

    label: str
    used: int
    limit: int | None
    unit: str = "tokens"
    reset_at: datetime | None = None

    @property
    def remaining(self) -> int | None:
        if self.limit is None:
            return None
        return max(self.limit - self.used, 0)

    @property
    def percent(self) -> float | None:
        if not self.limit:
            return None
        return min(self.used / self.limit * 100.0, 100.0)

    def reset_in_seconds(self, now: datetime | None = None) -> int | None:
        if self.reset_at is None:
            return None
        now = now or datetime.now(timezone.utc)
        delta = (self.reset_at - now).total_seconds()
        return max(int(delta), 0)


@dataclass
class ProviderStatus:
    """Everything needed to render one provider in the tray."""

    provider: str
    gauges: list[Gauge] = field(default_factory=list)
    detail: str | None = None  # e.g. "tier: build" or "updated 12s ago"
    error: str | None = None
    authenticated: bool = True

    @property
    def worst_percent(self) -> float | None:
        pcts = [g.percent for g in self.gauges if g.percent is not None]
        return max(pcts) if pcts else None
