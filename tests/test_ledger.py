from datetime import datetime, timedelta, timezone

from token_counter.ledger import Ledger


def test_record_and_aggregate(tmp_path):
    ledger = Ledger(tmp_path / "l.db")
    start = datetime(2026, 6, 1, tzinfo=timezone.utc)

    ledger.record("claude", "opus", input_tokens=100, output_tokens=50)
    ledger.record("claude", "opus", input_tokens=20, output_tokens=5)
    ledger.record("claude", "sonnet", input_tokens=10, output_tokens=10)

    usage = ledger.usage_since("claude", start)
    by_model = {m.model: m for m in usage}
    assert by_model["opus"].total == 175
    assert by_model["sonnet"].total == 20
    # ordered by total desc
    assert usage[0].model == "opus"


def test_provider_isolation(tmp_path):
    ledger = Ledger(tmp_path / "l.db")
    start = datetime(2026, 6, 1, tzinfo=timezone.utc)
    ledger.record("claude", "opus", input_tokens=100)
    ledger.record("gemini", "pro", input_tokens=999)
    assert sum(m.total for m in ledger.usage_since("claude", start)) == 100


def test_window_excludes_old_events(tmp_path):
    ledger = Ledger(tmp_path / "l.db")
    now = datetime.now(timezone.utc)
    old_ts = (now - timedelta(days=40)).timestamp()
    ledger.record("claude", "opus", input_tokens=500, ts=old_ts)
    ledger.record("claude", "opus", input_tokens=30)

    window = now - timedelta(days=30)
    usage = ledger.usage_since("claude", window)
    assert sum(m.total for m in usage) == 30


def test_cache_tokens_counted(tmp_path):
    ledger = Ledger(tmp_path / "l.db")
    start = datetime(2026, 6, 1, tzinfo=timezone.utc)
    ledger.record(
        "claude", "opus",
        input_tokens=10, output_tokens=5,
        cache_read_tokens=100, cache_creation_tokens=20,
    )
    usage = ledger.usage_since("claude", start)
    assert usage[0].total == 135
