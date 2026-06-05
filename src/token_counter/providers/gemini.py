"""Gemini (Google) provider — example/template.

Google does not return live per-request remaining-quota headers the way
Anthropic and OpenAI do, so the "rate_limit" provider can't read enforced
limits for it out of the box. Two practical options:

  1. **Manual ledger (what this does by default):** report usage from your code
     (the Gemini response carries ``usage_metadata``) and track it against a
     limit you set — same as ``local_ledger``.
  2. **Cloud Monitoring (pull):** if you run Gemini via Vertex AI on GCP,
     per-model token metrics are queryable from the Cloud Monitoring API.
     Implement that in ``_pull_from_monitoring`` and set ``use_monitoring: true``.

This is the copy-me template for wiring up a provider that lacks live headers.
"""

from __future__ import annotations

from datetime import datetime

from .base import Provider, register
from ..models import ProviderStatus
from .local_ledger import ledger_status


@register("gemini")
class GeminiProvider(Provider):
    auth_methods = ("api_key", "oauth")

    def poll(self, now: datetime | None = None) -> ProviderStatus:
        if self.config.option("use_monitoring", False):
            return self._pull_from_monitoring(self._now(now))
        return ledger_status(self, self._now(now))

    def validate_credential(self, secret: str) -> tuple[bool, str]:
        from .. import probe as probe_mod

        ok, msg, _headers = probe_mod.probe("google", secret)
        return ok, msg

    def _pull_from_monitoring(self, now: datetime) -> ProviderStatus:
        # TODO: query Cloud Monitoring token-count series per model.
        return ProviderStatus(
            provider=self.name,
            error="use_monitoring is not implemented yet; report usage to the local ledger instead",
        )
