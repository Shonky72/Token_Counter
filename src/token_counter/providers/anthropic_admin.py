"""Anthropic usage via the organization Usage & Cost API (optional "pull" example).

This polls ``/v1/organizations/usage_report/messages`` grouped by model and sums
the per-model token fields. It demonstrates the "remote pull" pattern for a
provider that exposes a usage API.

Caveats (surfaced here so they're not a surprise):
  * Requires an **Admin API key** (``sk-ant-admin...``), not a normal key.
  * The usage report has ingestion lag (minutes), so it is *not* strictly live
    within 30s. For true live tracking, report usage to the local ledger.
  * Field names below are summed defensively across known variants so a schema
    tweak degrades gracefully instead of breaking.

Config:
    - name: claude
      type: anthropic_admin
      admin_key_env: ANTHROPIC_ADMIN_KEY   # or admin_key: sk-ant-admin-...
      budget: { period: monthly, limit: 1000000 }
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from .base import Provider, register
from ..models import Gauge, ModelUsage, ProviderStatus

_ENDPOINT = "https://api.anthropic.com/v1/organizations/usage_report/messages"
_API_VERSION = "2023-06-01"

# Every field we treat as "tokens consumed", mapped onto our ModelUsage buckets.
_INPUT_FIELDS = ("uncached_input_tokens", "input_tokens")
_OUTPUT_FIELDS = ("output_tokens",)
_CACHE_READ_FIELDS = ("cache_read_input_tokens",)
_CACHE_CREATION_FIELDS = ("cache_creation_input_tokens", "cache_creation_tokens")


def _sum_fields(result: dict, fields: tuple[str, ...]) -> int:
    """Return the first present field's value, handling nested dict shapes."""
    for key in fields:
        if key in result and result[key] is not None:
            value = result[key]
            if isinstance(value, dict):  # e.g. cache_creation broken out by ttl
                return int(sum(v for v in value.values() if isinstance(v, (int, float))))
            return int(value)
    return 0


def _bucket_width(window_start: datetime, now: datetime) -> str:
    span_days = (now - window_start).total_seconds() / 86400
    if span_days <= 2:
        return "1m"
    return "1d"


@register("anthropic_admin")
class AnthropicAdminProvider(Provider):
    def _admin_key(self) -> str | None:
        key = self.config.secret("admin_key")
        if key:
            return key
        if self.store is not None:
            return self.store.get(self.name, "api_key")
        return None

    def poll(self, now: datetime | None = None) -> ProviderStatus:
        now = self._now(now)
        window_start = self.config.budget.window_start(now)
        key = self._admin_key()
        if not key:
            return ProviderStatus(
                provider=self.name,
                authenticated=False,
                error="missing admin_key (set admin_key_env to an env var holding sk-ant-admin-...)",
            )

        params = {
            "starting_at": window_start.astimezone(timezone.utc).isoformat(),
            "bucket_width": self.config.option("bucket_width", _bucket_width(window_start, now)),
            "group_by[]": "model",
            "limit": 100,
        }

        per_model: dict[str, ModelUsage] = {}
        next_page: str | None = None
        try:
            for _ in range(50):  # hard page cap, defensive against loops
                query = dict(params)
                if next_page:
                    query["page"] = next_page
                url = f"{_ENDPOINT}?{urllib.parse.urlencode(query)}"
                req = urllib.request.Request(
                    url,
                    headers={
                        "x-api-key": key,
                        "anthropic-version": _API_VERSION,
                    },
                )
                with urllib.request.urlopen(req, timeout=15) as resp:
                    payload = json.loads(resp.read().decode("utf-8"))

                for bucket in payload.get("data", []):
                    for result in bucket.get("results", []):
                        model = result.get("model") or "unknown"
                        usage = ModelUsage(
                            model=model,
                            input_tokens=_sum_fields(result, _INPUT_FIELDS),
                            output_tokens=_sum_fields(result, _OUTPUT_FIELDS),
                            cache_read_tokens=_sum_fields(result, _CACHE_READ_FIELDS),
                            cache_creation_tokens=_sum_fields(result, _CACHE_CREATION_FIELDS),
                        )
                        per_model[model] = (
                            per_model[model].merged_with(usage)
                            if model in per_model
                            else usage
                        )

                if not payload.get("has_more"):
                    break
                next_page = payload.get("next_page")
                if not next_page:
                    break
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:200] if exc.fp else ""
            return ProviderStatus(
                provider=self.name, error=f"HTTP {exc.code}: {detail or exc.reason}"
            )
        except (urllib.error.URLError, TimeoutError) as exc:
            return ProviderStatus(provider=self.name, error=f"network error: {exc}")
        except Exception as exc:  # pragma: no cover - defensive
            return ProviderStatus(provider=self.name, error=str(exc))

        models = sorted(per_model.values(), key=lambda m: m.total, reverse=True)
        budget = self.config.budget
        total = sum(m.total for m in models)
        gauges = [Gauge(label=f"total ({budget.period})", used=total, limit=budget.limit)]
        gauges += [
            Gauge(label=m.model, used=m.total, limit=budget.per_model.get(m.model))
            for m in models
        ]
        return ProviderStatus(provider=self.name, gauges=gauges, detail="Anthropic Usage API")

    def validate_credential(self, secret: str) -> tuple[bool, str]:
        if secret.startswith("sk-ant-admin"):
            return True, "saved (admin key)"
        if secret.strip():
            return True, "saved (warning: not an sk-ant-admin- key)"
        return False, "empty credential"
