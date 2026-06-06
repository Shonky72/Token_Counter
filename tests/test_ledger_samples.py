from datetime import datetime, timedelta, timezone

from token_counter.ledger import Ledger


def test_record_and_query_samples(tmp_path):
    led = Ledger(tmp_path / "l.db")
    now = datetime.now(timezone.utc).timestamp()
    led.record_sample("claude", used=10, limit=100, percent=10.0, ts=now - 60)
    led.record_sample("claude", used=20, limit=100, percent=20.0, ts=now - 30)
    led.record_sample("gemini", used=5, limit=None, percent=None, ts=now - 30)

    start = datetime.now(timezone.utc) - timedelta(hours=1)
    rows = led.samples_since("claude", start)
    assert [u for _, u in rows] == [10, 20]
    assert len(led.samples_since("gemini", start)) == 1


def test_prune_samples(tmp_path):
    led = Ledger(tmp_path / "l.db")
    now = datetime.now(timezone.utc).timestamp()
    led.record_sample("claude", used=1, ts=now - 10 * 86400)  # 10 days old
    led.record_sample("claude", used=2, ts=now - 60)
    led.prune_samples(datetime.now(timezone.utc) - timedelta(days=7))
    start = datetime.now(timezone.utc) - timedelta(days=30)
    assert [u for _, u in led.samples_since("claude", start)] == [2]
