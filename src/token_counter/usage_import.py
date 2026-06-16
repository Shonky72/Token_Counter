"""Import historical usage from a CSV into the local ledger.

Individual Anthropic/Google accounts expose no programmatic usage API, so the only
way to *display* past usage is to read the per-day, per-model totals off the
provider's Console and import them here. Each row becomes a back-dated
``usage_events`` entry, after which the ledger-backed card (``local_ledger`` for
Claude, ``gemini`` for Gemini) shows the cumulative total and estimated cost.

CSV is forgiving: a header row with any reasonable spelling of date / model /
input / output (and optional cache columns). Example::

    date,model,input_tokens,output_tokens
    2026-06-15,claude-haiku-4-5,109157,63699
    2026-06-10,claude-haiku-4-5,21000,0
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

# header alias -> canonical field (compared case-insensitively, spaces/underscores
# stripped, trailing "tokens" removed, e.g. "Input Tokens" -> "input").
_ALIASES = {
    "date": "date", "day": "date", "timestamp": "date", "ts": "date",
    "start": "date", "startingat": "date", "bucket": "date", "time": "date",
    "model": "model", "modelname": "model", "modelid": "model",
    "input": "input", "in": "input", "uncachedinput": "input", "prompt": "input",
    "output": "output", "out": "output", "completion": "output",
    "cacheread": "cache_read", "cachereadinput": "cache_read",
    "cachecreation": "cache_creation", "cachecreationinput": "cache_creation",
    "cachewrite": "cache_creation",
}

_DATE_FORMATS = ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m", "%Y/%m", "%d-%m-%Y", "%m/%d/%Y")


def _canon(header: str) -> str | None:
    key = "".join(header.lower().split()).replace("_", "").replace("-", "")
    if key.endswith("tokens"):
        key = key[: -len("tokens")]
    return _ALIASES.get(key)


def _to_int(value: str | None) -> int:
    if value is None:
        return 0
    s = str(value).strip().replace(",", "")
    if not s:
        return 0
    try:
        return int(float(s))
    except ValueError:
        return 0


def parse_date(value: str | None) -> float:
    """A date/datetime string -> UTC epoch (noon, so month-window filters include
    it). Empty/unparseable -> now."""
    s = (value or "").strip()
    if not s:
        return datetime.now(timezone.utc).timestamp()
    try:  # ISO datetime (e.g. an Anthropic ``starting_at``)
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except ValueError:
        pass
    for fmt in _DATE_FORMATS:
        try:
            dt = datetime.strptime(s, fmt).replace(hour=12, tzinfo=timezone.utc)
            return dt.timestamp()
        except ValueError:
            continue
    return datetime.now(timezone.utc).timestamp()


def parse_rows(path: str | Path) -> list[dict]:
    """Parse a usage CSV into ``{ts, model, input/output/cache_* tokens}`` dicts."""
    text = Path(path).expanduser().read_text(encoding="utf-8-sig")
    reader = csv.reader(text.splitlines())
    rows = list(reader)
    if not rows:
        return []
    header = [_canon(h) for h in rows[0]]
    if "input" not in header and "output" not in header:
        raise ValueError(
            "CSV needs a header row with at least 'input_tokens' and/or "
            "'output_tokens' columns (plus optional 'date' and 'model')."
        )
    out: list[dict] = []
    for raw in rows[1:]:
        if not any(c.strip() for c in raw):
            continue
        rec = {h: raw[i] for i, h in enumerate(header) if h and i < len(raw)}
        item = {
            "ts": parse_date(rec.get("date")),
            "model": (rec.get("model") or "imported").strip() or "imported",
            "input_tokens": _to_int(rec.get("input")),
            "output_tokens": _to_int(rec.get("output")),
            "cache_read_tokens": _to_int(rec.get("cache_read")),
            "cache_creation_tokens": _to_int(rec.get("cache_creation")),
        }
        out.append(item)
    return out


def import_rows(ledger, provider: str, rows: list[dict]) -> tuple[int, int]:
    """Record each row under ``provider``. Returns (event_count, total_tokens)."""
    total = 0
    for r in rows:
        ledger.record(
            provider=provider,
            model=r["model"],
            input_tokens=r["input_tokens"],
            output_tokens=r["output_tokens"],
            cache_read_tokens=r["cache_read_tokens"],
            cache_creation_tokens=r["cache_creation_tokens"],
            ts=r["ts"],
        )
        total += (r["input_tokens"] + r["output_tokens"]
                  + r["cache_read_tokens"] + r["cache_creation_tokens"])
    return len(rows), total


def import_csv(ledger, provider: str, path: str | Path) -> tuple[int, int]:
    return import_rows(ledger, provider, parse_rows(path))


# Route a row to the right ledger-backed card from its model name, so one
# "Import usage" button can handle a mixed CSV with no service picker.
_MODEL_SERVICE = (
    (("claude", "anthropic", "opus", "sonnet", "haiku"), "claude_tracked"),
    (("gemini", "google", "bison", "gemma", "palm"), "gemini"),
)


def provider_for_model(model: str | None) -> str | None:
    m = (model or "").lower()
    for needles, prov in _MODEL_SERVICE:
        if any(n in m for n in needles):
            return prov
    return None


def import_auto(ledger, path: str | Path, ensure=None) -> tuple[dict, int]:
    """Import a CSV, routing each row to a card by model name.

    ``ensure(provider)`` is called once per detected provider (e.g. to add the
    config card). Returns ``({provider: (count, total)}, unknown_row_count)``.
    """
    buckets: dict[str, list[dict]] = {}
    unknown = 0
    for row in parse_rows(path):
        prov = provider_for_model(row.get("model"))
        if prov is None:
            unknown += 1
            continue
        buckets.setdefault(prov, []).append(row)
    result: dict[str, tuple[int, int]] = {}
    for prov, rows in buckets.items():
        if ensure is not None:
            try:
                ensure(prov)
            except Exception:
                pass
        result[prov] = import_rows(ledger, prov, rows)
    return result, unknown

