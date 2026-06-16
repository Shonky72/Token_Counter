from datetime import datetime, timedelta, timezone

from token_counter import usage_import
from token_counter.config import ensure_provider, load_config
from token_counter.ledger import Ledger


def _write(path, text):
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_parse_rows_flexible_headers(tmp_path):
    csv = _write(tmp_path / "u.csv",
                 "Date,Model,Input Tokens,Output Tokens\n"
                 "2026-06-15,claude-haiku-4-5,109157,63699\n"
                 "2026-06-10,claude-haiku-4-5,21000,0\n")
    rows = usage_import.parse_rows(csv)
    assert len(rows) == 2
    assert rows[0]["model"] == "claude-haiku-4-5"
    assert rows[0]["input_tokens"] == 109157 and rows[0]["output_tokens"] == 63699
    # date parsed onto the right day (UTC)
    d = datetime.fromtimestamp(rows[0]["ts"], tz=timezone.utc)
    assert (d.year, d.month, d.day) == (2026, 6, 15)


def test_parse_rows_handles_commas_and_blank_lines(tmp_path):
    csv = _write(tmp_path / "u.csv",
                 "date,model,input_tokens,output_tokens\n"
                 "2026-06-01,gemini-2.5-pro,\"1,200,000\",\"600,000\"\n"
                 "\n")
    rows = usage_import.parse_rows(csv)
    assert len(rows) == 1
    assert rows[0]["input_tokens"] == 1200000 and rows[0]["output_tokens"] == 600000


def test_parse_rows_requires_token_columns(tmp_path):
    import pytest

    csv = _write(tmp_path / "bad.csv", "date,model\n2026-06-01,x\n")
    with pytest.raises(ValueError):
        usage_import.parse_rows(csv)


def test_parse_date_fallback_to_now():
    before = datetime.now(timezone.utc).timestamp() - 5
    assert usage_import.parse_date("") >= before
    assert usage_import.parse_date("not-a-date") >= before


def test_import_rows_records_into_ledger(tmp_path):
    ledger = Ledger(tmp_path / "ledger.db")
    csv = _write(tmp_path / "u.csv",
                 "date,model,input_tokens,output_tokens\n"
                 "2026-06-15,claude-haiku-4-5,100000,50000\n"
                 "2026-06-10,claude-opus-4-8,2000,1000\n")
    count, total = usage_import.import_csv(ledger, "claude_tracked", csv)
    assert count == 2
    assert total == 100000 + 50000 + 2000 + 1000

    start = datetime(2026, 6, 1, tzinfo=timezone.utc)
    models = ledger.usage_since("claude_tracked", start)
    by_model = {m.model: m.total for m in models}
    assert by_model["claude-haiku-4-5"] == 150000
    assert by_model["claude-opus-4-8"] == 3000

    # back-dated: events dated in June are NOT counted from a July window start
    july = datetime(2026, 7, 1, tzinfo=timezone.utc)
    assert ledger.usage_since("claude_tracked", july) == []


def test_provider_for_model_routing():
    assert usage_import.provider_for_model("claude-haiku-4-5") == "claude_tracked"
    assert usage_import.provider_for_model("claude-opus-4-8") == "claude_tracked"
    assert usage_import.provider_for_model("gemini-2.5-pro") == "gemini"
    assert usage_import.provider_for_model("gpt-4o-mini") is None
    assert usage_import.provider_for_model("") is None


def test_import_auto_routes_mixed_csv(tmp_path):
    ledger = Ledger(tmp_path / "ledger.db")
    csv = _write(tmp_path / "mixed.csv",
                 "date,model,input_tokens,output_tokens\n"
                 "2026-06-15,claude-haiku-4-5,100000,50000\n"
                 "2026-06-15,gemini-2.5-pro,8000,2000\n"
                 "2026-06-15,gpt-4o-mini,500,500\n")
    seen = []
    result, unknown = usage_import.import_auto(ledger, csv, ensure=seen.append)
    assert result["claude_tracked"] == (1, 150000)
    assert result["gemini"] == (1, 10000)
    assert unknown == 1  # the gpt row has no ledger-backed card
    assert set(seen) == {"claude_tracked", "gemini"}

    start = datetime(2026, 6, 1, tzinfo=timezone.utc)
    assert sum(m.total for m in ledger.usage_since("claude_tracked", start)) == 150000
    assert sum(m.total for m in ledger.usage_since("gemini", start)) == 10000


def test_ensure_provider_adds_card_idempotently(tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("providers: []\n", encoding="utf-8")
    assert ensure_provider(cfg, "claude_tracked") is True
    assert ensure_provider(cfg, "claude_tracked") is False  # already present
    parsed = load_config(cfg)
    names = {p.name: p for p in parsed.providers}
    assert "claude_tracked" in names
    assert names["claude_tracked"].type == "local_ledger"
