from datetime import datetime, timedelta, timezone

from token_counter.config import parse_config
from token_counter.ledger import Ledger
from token_counter.providers import create_provider


def _provider(tmp_path):
    cfg = parse_config(
        {"providers": [{"name": "claude", "type": "rate_limit", "scheme": "anthropic"}]}
    )
    ledger = Ledger(tmp_path / "l.db")
    return create_provider(cfg.providers[0], ledger), ledger


def test_gauge_used_is_limit_minus_remaining(tmp_path):
    provider, ledger = _provider(tmp_path)
    ledger.save_rate_limits(
        "claude", {"tokens": {"limit": 1000, "remaining": 250, "reset_at": None, "unit": "tokens"}}
    )
    status = provider.poll(datetime.now(timezone.utc))
    g = status.gauges[0]
    assert g.used == 750 and g.remaining == 250


def test_window_rolls_over_to_full_after_reset(tmp_path):
    provider, ledger = _provider(tmp_path)
    past = (datetime.now(timezone.utc) - timedelta(seconds=10)).timestamp()
    ledger.save_rate_limits(
        "claude", {"tokens": {"limit": 1000, "remaining": 50, "reset_at": past, "unit": "tokens"}}
    )
    status = provider.poll(datetime.now(timezone.utc))
    # reset is in the past -> treated as replenished
    assert status.gauges[0].used == 0


def test_window_not_rolled_before_reset(tmp_path):
    provider, ledger = _provider(tmp_path)
    future = (datetime.now(timezone.utc) + timedelta(seconds=30)).timestamp()
    ledger.save_rate_limits(
        "claude", {"tokens": {"limit": 1000, "remaining": 50, "reset_at": future, "unit": "tokens"}}
    )
    status = provider.poll(datetime.now(timezone.utc))
    assert status.gauges[0].used == 950
