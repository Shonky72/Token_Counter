"""The engine: build providers from config and compute budget statuses.

This is the headless heart of the app — no tray, no threads. Given a config and
a ledger it produces a list of ``BudgetStatus`` you can render anywhere (tray
tooltip, CLI ``status``, a future web page).
"""

from __future__ import annotations

from datetime import datetime, timezone

from .config import AppConfig
from .ledger import Ledger
from .models import BudgetStatus, ModelBudgetStatus, ProviderUsage
from .providers import create_provider


class Engine:
    def __init__(self, config: AppConfig, ledger: Ledger):
        self.config = config
        self.ledger = ledger
        self._providers = {
            pc.name: create_provider(pc, ledger) for pc in config.providers
        }

    def _status_for(self, provider_cfg, usage: ProviderUsage) -> BudgetStatus:
        budget = provider_cfg.budget
        used_by_model = {m.model: m.total for m in usage.models}

        model_statuses = [
            ModelBudgetStatus(
                model=model,
                used=used,
                limit=budget.per_model.get(model),
            )
            for model, used in sorted(
                used_by_model.items(), key=lambda kv: kv[1], reverse=True
            )
        ]
        # Surface configured per-model budgets even before any usage exists.
        for model, limit in budget.per_model.items():
            if model not in used_by_model:
                model_statuses.append(ModelBudgetStatus(model=model, used=0, limit=limit))

        return BudgetStatus(
            provider=provider_cfg.name,
            period=budget.period,
            limit=budget.limit,
            used=usage.total,
            models=model_statuses,
            error=usage.error,
        )

    def snapshot(self, now: datetime | None = None) -> list[BudgetStatus]:
        now = now or datetime.now(timezone.utc)
        statuses: list[BudgetStatus] = []
        for provider_cfg in self.config.providers:
            provider = self._providers[provider_cfg.name]
            window_start = provider_cfg.budget.window_start(now)
            usage = provider.get_usage(window_start)
            statuses.append(self._status_for(provider_cfg, usage))
        return statuses
