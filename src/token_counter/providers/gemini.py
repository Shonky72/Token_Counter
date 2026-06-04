"""Gemini (Google) provider — example scaffold.

Google's Generative Language API does not expose a simple, live, per-model token
usage endpoint the way this widget wants. Two practical paths:

  1. **Local ledger (recommended, what this scaffold does):** report usage from
     your own code after each ``generate_content`` call. The Gemini response
     carries ``usage_metadata`` (prompt_token_count, candidates_token_count,
     total_token_count) — POST those to the local server. This subclass simply
     reads that ledger, so it behaves identically to ``local_ledger`` but exists
     as a clearly-named, copy-me starting point for a real pull integration.

  2. **Cloud Monitoring (pull):** if you run Gemini through Vertex AI on GCP,
     per-model token metrics are available via the Cloud Monitoring API
     (``aiplatform.googleapis.com`` token-count series). Implement that in
     ``_pull_from_monitoring`` and flip ``use_monitoring: true`` in config.

This is intentionally the template a user copies to wire up "any provider I
choose".
"""

from __future__ import annotations

from datetime import datetime

from .base import Provider, register
from ..models import ProviderUsage


@register("gemini")
class GeminiProvider(Provider):
    def get_usage(self, window_start: datetime) -> ProviderUsage:
        if self.config.option("use_monitoring", False):
            return self._pull_from_monitoring(window_start)
        # Default: ledger-backed, exact and live.
        try:
            models = self.ledger.usage_since(self.name, window_start)
            return ProviderUsage(provider=self.name, models=models)
        except Exception as exc:  # pragma: no cover - defensive
            return ProviderUsage(provider=self.name, error=str(exc))

    def _pull_from_monitoring(self, window_start: datetime) -> ProviderUsage:
        # TODO: query Cloud Monitoring time series for token counts per model.
        # Left as a clearly-marked extension point rather than a broken stub.
        return ProviderUsage(
            provider=self.name,
            error="use_monitoring is not implemented yet; report usage to the local ledger instead",
        )
