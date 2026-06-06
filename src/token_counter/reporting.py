"""Export recorded usage (from the ledger) as CSV or JSON.

Covers the per-model token totals each provider has accumulated since a start
time, with an approximate $ estimate from ``pricing``. Used by the ``export`` CLI
subcommand and the Settings → Data → Export… button.
"""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime

from . import pricing

FIELDS = [
    "provider", "model", "input_tokens", "output_tokens",
    "cache_read_tokens", "cache_creation_tokens", "total_tokens", "est_cost_usd",
]


def collect_rows(ledger, providers: list[str], start: datetime) -> list[dict]:
    """One row per (provider, model) with token totals + estimated cost."""
    rows: list[dict] = []
    for provider in providers:
        for u in ledger.usage_since(provider, start):
            cost = pricing.estimate_cost(
                u.model, u.input_tokens, u.output_tokens,
                u.cache_read_tokens, u.cache_creation_tokens,
            )
            rows.append({
                "provider": provider,
                "model": u.model,
                "input_tokens": u.input_tokens,
                "output_tokens": u.output_tokens,
                "cache_read_tokens": u.cache_read_tokens,
                "cache_creation_tokens": u.cache_creation_tokens,
                "total_tokens": u.total,
                "est_cost_usd": round(cost, 4) if cost else 0.0,
            })
    return rows


def export_usage(ledger, providers: list[str], start: datetime, fmt: str = "json") -> str:
    """Return CSV or JSON text for usage since ``start``."""
    rows = collect_rows(ledger, providers, start)
    if fmt == "csv":
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=FIELDS)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
        return buf.getvalue()
    payload = {
        "exported_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "since": start.astimezone().isoformat(timespec="seconds"),
        "rows": rows,
        "total_est_cost_usd": round(sum(r["est_cost_usd"] for r in rows), 4),
    }
    return json.dumps(payload, indent=2)
