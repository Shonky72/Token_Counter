from token_counter.ledger import Ledger


def test_save_and_get_rate_limits(tmp_path):
    ledger = Ledger(tmp_path / "l.db")
    windows = {"tokens": {"limit": 40000, "remaining": 100, "reset_at": 123.0, "unit": "tokens"}}
    ledger.save_rate_limits("claude", windows, captured_at=1000.0)

    snap = ledger.get_rate_limits("claude")
    assert snap is not None
    captured_at, got = snap
    assert captured_at == 1000.0
    assert got["tokens"]["limit"] == 40000


def test_rate_limits_upsert_overwrites(tmp_path):
    ledger = Ledger(tmp_path / "l.db")
    ledger.save_rate_limits("claude", {"tokens": {"limit": 1}}, captured_at=1.0)
    ledger.save_rate_limits("claude", {"tokens": {"limit": 2}}, captured_at=2.0)
    captured_at, got = ledger.get_rate_limits("claude")
    assert captured_at == 2.0
    assert got["tokens"]["limit"] == 2


def test_get_rate_limits_missing(tmp_path):
    ledger = Ledger(tmp_path / "l.db")
    assert ledger.get_rate_limits("nope") is None
