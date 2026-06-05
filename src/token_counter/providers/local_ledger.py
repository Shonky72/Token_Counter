"""Manual-budget provider: usage from the local ledger vs. a limit you set.

Kept for cases where you want to track consumption against your own allowance
(rather than the provider-enforced rate limits). Usage is summed from the
ledger; the limit comes from ``budget`` in config.
"""

from __future__ import annotations

from datetime import datetime

from .base import Provider, register
from ..models import Gauge, ProviderStatus


def ledger_status(provider: "Provider", now: datetime) -> ProviderStatus:
    """Shared helper: build a ProviderStatus from ledger usage + config budget."""
    budget = provider.config.budget
    window_start = budget.window_start(now)
    try:
        models = provider.ledger.usage_since(provider.name, window_start)
    except Exception as exc:  # pragma: no cover - defensive
        return ProviderStatus(provider=provider.name, error=str(exc))

    total = sum(m.total for m in models)
    gauges = [
        Gauge(
            label=f"total ({budget.period})",
            used=total,
            limit=budget.limit,
        )
    ]
    used_by_model = {m.model: m.total for m in models}
    for model, used in sorted(used_by_model.items(), key=lambda kv: kv[1], reverse=True):
        gauges.append(Gauge(label=model, used=used, limit=budget.per_model.get(model)))
    for model, limit in budget.per_model.items():
        if model not in used_by_model:
            gauges.append(Gauge(label=model, used=0, limit=limit))
    return ProviderStatus(provider=provider.name, gauges=gauges, detail=f"{budget.period} budget")


@register("local_ledger")
class LocalLedgerProvider(Provider):
    def poll(self, now: datetime | None = None) -> ProviderStatus:
        return ledger_status(self, self._now(now))
