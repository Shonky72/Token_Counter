from datetime import datetime, timezone

from token_counter.config import parse_config
from token_counter.engine import Engine
from token_counter.ledger import Ledger


def _engine(tmp_path, raw):
    config = parse_config(raw)
    ledger = Ledger(tmp_path / "l.db")
    return Engine(config, ledger), ledger


def test_used_and_remaining(tmp_path):
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
    assert status.used == 700
    assert status.limit == 1000
    assert status.remaining == 300
    assert round(status.percent) == 70


def test_remaining_clamps_at_zero(tmp_path):
    engine, ledger = _engine(
        tmp_path,
        {"providers": [{"name": "c", "type": "local_ledger", "budget": {"period": "total", "limit": 100}}]},
    )
    ledger.record("c", "opus", input_tokens=250)
    [status] = engine.snapshot()
    assert status.remaining == 0
    assert status.percent == 100


def test_per_model_budgets_surface_even_without_usage(tmp_path):
    engine, _ = _engine(
        tmp_path,
        {
            "providers": [
                {
                    "name": "c",
                    "type": "local_ledger",
                    "budget": {"period": "total", "limit": 1000, "per_model": {"opus": 500}},
                }
            ]
        },
    )
    [status] = engine.snapshot()
    opus = next(m for m in status.models if m.model == "opus")
    assert opus.limit == 500
    assert opus.used == 0
    assert opus.remaining == 500


def test_no_limit_means_no_percent(tmp_path):
    engine, ledger = _engine(
        tmp_path,
        {"providers": [{"name": "c", "type": "local_ledger", "budget": {"period": "total"}}]},
    )
    ledger.record("c", "opus", input_tokens=42)
    [status] = engine.snapshot()
    assert status.limit is None
    assert status.percent is None
    assert status.remaining is None
    assert status.used == 42


def test_unknown_provider_type_errors(tmp_path):
    import pytest

    with pytest.raises(ValueError):
        _engine(tmp_path, {"providers": [{"name": "c", "type": "does_not_exist"}]})
