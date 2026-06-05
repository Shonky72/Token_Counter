"""The engine: build providers from config and collect their statuses.

Headless heart of the app — no tray, no threads. With provider-enforced limits,
each provider returns its own ``ProviderStatus`` (limits included), so the engine
just builds the providers and polls them.
"""

from __future__ import annotations

from datetime import datetime, timezone

from .config import AppConfig
from .ledger import Ledger
from .models import ProviderStatus
from .providers import create_provider


class Engine:
    def __init__(self, config: AppConfig, ledger: Ledger, store=None):
        self.config = config
        self.ledger = ledger
        self.store = store
        self.providers = {
            pc.name: create_provider(pc, ledger, store) for pc in config.providers
        }

    def snapshot(self, now: datetime | None = None) -> list[ProviderStatus]:
        now = now or datetime.now(timezone.utc)
        statuses: list[ProviderStatus] = []
        for pc in self.config.providers:
            try:
                statuses.append(self.providers[pc.name].poll(now))
            except Exception as exc:  # pragma: no cover - keep the loop alive
                statuses.append(ProviderStatus(provider=pc.name, error=str(exc)))
        return statuses
