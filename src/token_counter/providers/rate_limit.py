"""Provider-enforced rate-limit gauges, read live from API response headers.

This is the default provider for the "API rate limits (live)" mode. It does not
hold any hand-entered numbers: the limit/remaining/reset come straight from the
provider's own response headers, captured by the local sidecar as your code
makes real calls (see ``server.py`` ``POST /ratelimit`` and
``examples/report_usage.py``).

Config::

    - name: claude
      type: rate_limit
      scheme: anthropic        # anthropic | openai | google | auto
      # probe: true            # optional: actively hit /models on each refresh

Window semantics: rate-limit windows replenish continuously. We show the
last-captured remaining, and once ``reset_at`` passes we optimistically roll the
gauge back to full (used = 0) so an idle widget reads sensibly.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

from .base import Provider, register
from .. import probe as probe_mod
from ..models import Gauge, ProviderStatus

_UNIT_LABEL = {"tokens": "tokens/min", "requests": "requests/min"}
_WINDOW_LABEL = {
    "tokens": "tokens/min",
    "requests": "requests/min",
    "input_tokens": "input tokens/min",
    "output_tokens": "output tokens/min",
}


@register("rate_limit")
class RateLimitProvider(Provider):
    auth_methods = ("api_key", "oauth")

    @property
    def scheme(self) -> str:
        return str(self.config.option("scheme", "auto"))

    @property
    def base_url(self) -> str | None:
        return self.config.option("base_url")

    @property
    def test_model(self) -> str | None:
        return self.config.option("test_model")

    def validate_credential(self, secret: str) -> tuple[bool, str]:
        from ..ratelimit import parse_headers

        # First confirm the key works (cheap list-models call).
        ok, msg, headers = probe_mod.probe(self.scheme, secret, self.base_url)
        if not ok:
            return ok, msg

        # Then fetch live rate-limit headers with one tiny generation call so the
        # gauge is populated immediately (fixes "no rate-limit data yet").
        _f_ok, _f_msg, f_headers = probe_mod.fetch_rate_limits(
            self.scheme, secret, self.base_url, self.test_model)
        windows = parse_headers(f_headers or headers, self.scheme)
        if windows:
            self.ledger.save_rate_limits(self.name, windows)
            return True, "saved · live limits loaded"
        return True, "saved (limits will appear after your first API call)"

    def _maybe_probe(self) -> None:
        if not self.config.option("probe", False):
            return
        secret = self.api_key()
        if not secret:
            return
        ok, _msg, headers = probe_mod.probe(self.scheme, secret, self.base_url)
        if ok and headers:
            from ..ratelimit import parse_headers

            windows = parse_headers(headers, self.scheme)
            if windows:
                self.ledger.save_rate_limits(self.name, windows)

    def poll(self, now: datetime | None = None) -> ProviderStatus:
        now = self._now(now)
        try:
            self._maybe_probe()
            snapshot = self.ledger.get_rate_limits(self.name)
        except Exception as exc:  # pragma: no cover - defensive
            return ProviderStatus(provider=self.name, error=str(exc))

        if snapshot is None:
            return ProviderStatus(
                provider=self.name,
                error="no rate-limit data yet — make an API call (and forward its headers)",
                detail="waiting for first response headers",
            )

        captured_at, windows = snapshot
        gauges = [
            self._gauge(name, w, now) for name, w in windows.items() if self._gauge(name, w, now)
        ]
        age = max(int(time.time() - captured_at), 0)
        return ProviderStatus(
            provider=self.name,
            gauges=[g for g in gauges if g is not None],
            detail=f"updated {age}s ago",
        )

    def _gauge(self, name: str, w: dict, now: datetime) -> Gauge | None:
        limit = w.get("limit")
        remaining = w.get("remaining")
        if limit is None and remaining is None:
            return None
        reset_at = w.get("reset_at")
        reset_dt = (
            datetime.fromtimestamp(reset_at, tz=timezone.utc) if reset_at else None
        )

        if limit is not None and remaining is not None:
            used = max(limit - remaining, 0)
        else:
            used = 0
        # Window has rolled over since capture: treat as replenished to full.
        if reset_at is not None and now.timestamp() >= reset_at:
            used = 0

        return Gauge(
            label=_WINDOW_LABEL.get(name, name),
            used=used,
            limit=limit,
            unit=w.get("unit", "tokens"),
            reset_at=reset_dt,
        )
