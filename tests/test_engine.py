import pytest

from token_counter.config import parse_config
from token_counter.engine import Engine
from token_counter.ledger import Ledger


def _engine(tmp_path, raw):
    config = parse_config(raw)
    ledger = Ledger(tmp_path / "l.db")
    return Engine(config, ledger), ledger


def test_ledger_provider_used_and_remaining(tmp_path):
    engine, ledger = _engine(
        tmp_path,
        {
            "providers": [
                {
                    "name": "claude",
                    "type": "local_ledger",
                    "budget": {"period": "total", "limit": 1000},
                }
            ]
        },
    )
    ledger.record("claude", "opus", input_tokens=600, output_tokens=100)
    [status] = engine.snapshot()
    total_gauge = status.gauges[0]
    assert total_gauge.used == 700
    assert total_gauge.limit == 1000
    assert total_gauge.remaining == 300
    assert round(total_gauge.percent) == 70


def test_rate_limit_provider_reads_enforced_limits(tmp_path):
    engine, ledger = _engine(
        tmp_path,
        {"providers": [{"name": "claude", "type": "rate_limit", "scheme": "anthropic"}]},
    )
    # Simulate captured headers (limit 40k, 12k remaining -> 28k used).
    ledger.save_rate_limits(
        "claude",
        {"tokens": {"limit": 40000, "remaining": 12000, "reset_at": None, "unit": "tokens"}},
    )
    [status] = engine.snapshot()
    assert status.error is None
    g = status.gauges[0]
    assert g.limit == 40000
    assert g.used == 28000
    assert g.remaining == 12000


def test_rate_limit_provider_without_data_errors_cleanly(tmp_path):
    engine, _ = _engine(
        tmp_path,
        {"providers": [{"name": "claude", "type": "rate_limit", "scheme": "anthropic"}]},
    )
    [status] = engine.snapshot()
    assert status.error is not None
    assert "no rate-limit data" in status.error


def test_unknown_provider_type_errors(tmp_path):
    with pytest.raises(ValueError):
        _engine(tmp_path, {"providers": [{"name": "c", "type": "does_not_exist"}]})


def test_engine_isolates_provider_failures(tmp_path):
    # A provider that raises should not break the whole snapshot.
    engine, _ = _engine(
        tmp_path,
        {
            "providers": [
                {"name": "ok", "type": "rate_limit", "scheme": "anthropic"},
            ]
        },
    )

    def boom(now=None):
        raise RuntimeError("kaboom")

    engine.providers["ok"].poll = boom
    [status] = engine.snapshot()
    assert "kaboom" in status.error
