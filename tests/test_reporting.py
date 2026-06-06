import json
from datetime import datetime, timedelta, timezone

from token_counter import reporting
from token_counter.ledger import Ledger


def _ledger(tmp_path):
    led = Ledger(tmp_path / "l.db")
    led.record("openai", "gpt-4o", input_tokens=1_000_000, output_tokens=0)
    led.record("openai", "mystery", input_tokens=500)
    return led


def test_collect_rows(tmp_path):
    led = _ledger(tmp_path)
    start = datetime.now(timezone.utc) - timedelta(days=1)
    rows = reporting.collect_rows(led, ["openai"], start)
    models = {r["model"]: r for r in rows}
    assert models["gpt-4o"]["est_cost_usd"] == 2.5     # 1M input @ $2.50
    assert models["mystery"]["est_cost_usd"] == 0.0


def test_export_json_shape(tmp_path):
    led = _ledger(tmp_path)
    start = datetime.now(timezone.utc) - timedelta(days=1)
    text = reporting.export_usage(led, ["openai"], start, "json")
    data = json.loads(text)
    assert "rows" in data and "total_est_cost_usd" in data
    assert data["total_est_cost_usd"] == 2.5


def test_export_csv_header(tmp_path):
    led = _ledger(tmp_path)
    start = datetime.now(timezone.utc) - timedelta(days=1)
    text = reporting.export_usage(led, ["openai"], start, "csv")
    first = text.splitlines()[0]
    assert first.startswith("provider,model,input_tokens")
