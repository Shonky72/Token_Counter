"""Core data structures shared across the app.

These are deliberately plain dataclasses with no I/O so they are trivial to
construct in tests and to pass between the ledger, providers, engine and tray.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ModelUsage:
    """Token usage for a single model within some time window."""

    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0

    @property
    def total(self) -> int:
        """Every token that counts against an allowance."""
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
class ProviderUsage:
    """What a provider reports for the current budget window.

    ``error`` is set when the provider could not be polled (bad key, network,
    etc.). The tray surfaces this rather than silently showing stale zeros.
    """

    provider: str
    models: list[ModelUsage] = field(default_factory=list)
    error: str | None = None

    @property
    def total(self) -> int:
        return sum(m.total for m in self.models)


@dataclass
class ModelBudgetStatus:
    model: str
    used: int
    limit: int | None  # None => no per-model cap configured

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


@dataclass
class BudgetStatus:
    """The computed used/remaining picture for one provider, ready to render."""

    provider: str
    period: str
    limit: int | None
    used: int
    models: list[ModelBudgetStatus] = field(default_factory=list)
    error: str | None = None

    @property
    def remaining(self) -> int | None:
        if self.limit is None:
            return None
        return max(self.limit - self.used, 0)

    @property
    def percent(self) -> float | None:
        """Percent of the allowance consumed, 0-100, or None if no limit set."""
        if not self.limit:
            return None
        return min(self.used / self.limit * 100.0, 100.0)
