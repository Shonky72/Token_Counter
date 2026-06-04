"""The reliable, provider-agnostic source: the local usage ledger.

Use this ``type`` for any provider whose usage you report yourself (via the
HTTP server or ``token-counter record``). It is exact and live within one
refresh interval, which is why it's the recommended default for "any provider
I choose".
"""

from __future__ import annotations

from datetime import datetime

from .base import Provider, register
from ..models import ProviderUsage


@register("local_ledger")
class LocalLedgerProvider(Provider):
    def get_usage(self, window_start: datetime) -> ProviderUsage:
        try:
            models = self.ledger.usage_since(self.name, window_start)
            return ProviderUsage(provider=self.name, models=models)
        except Exception as exc:  # pragma: no cover - defensive
            return ProviderUsage(provider=self.name, error=str(exc))
