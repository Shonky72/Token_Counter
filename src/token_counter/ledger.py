"""A small, durable usage ledger backed by SQLite.

Every LLM call your code makes can report its token usage here (via the local
HTTP server or the ``record`` CLI). This is the source of truth that makes the
counter genuinely live: an event written now is visible to the next 30s refresh.
"""

from __future__ import annotations

import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from .models import ModelUsage

_SCHEMA = """
CREATE TABLE IF NOT EXISTS usage_events (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    ts                    REAL NOT NULL,          -- UTC epoch seconds
    provider              TEXT NOT NULL,
    model                 TEXT NOT NULL,
    input_tokens          INTEGER NOT NULL DEFAULT 0,
    output_tokens         INTEGER NOT NULL DEFAULT 0,
    cache_read_tokens     INTEGER NOT NULL DEFAULT 0,
    cache_creation_tokens INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_usage_lookup ON usage_events (provider, ts);
"""


class Ledger:
    """Thread-safe usage store. Cheap to construct; opens one connection."""

    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False because the HTTP server and poller threads
        # both touch it; all access is guarded by self._lock.
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    def record(
        self,
        provider: str,
        model: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cache_read_tokens: int = 0,
        cache_creation_tokens: int = 0,
        ts: float | None = None,
    ) -> None:
        if ts is None:
            ts = time.time()
        with self._lock:
            self._conn.execute(
                """INSERT INTO usage_events
                   (ts, provider, model, input_tokens, output_tokens,
                    cache_read_tokens, cache_creation_tokens)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    ts,
                    provider,
                    model,
                    int(input_tokens),
                    int(output_tokens),
                    int(cache_read_tokens),
                    int(cache_creation_tokens),
                ),
            )
            self._conn.commit()

    def usage_since(self, provider: str, start: datetime) -> list[ModelUsage]:
        """Aggregate usage for ``provider`` since ``start`` (inclusive), per model."""
        start_ts = start.astimezone(timezone.utc).timestamp()
        with self._lock:
            rows = self._conn.execute(
                """SELECT model,
                          SUM(input_tokens)          AS input_tokens,
                          SUM(output_tokens)         AS output_tokens,
                          SUM(cache_read_tokens)     AS cache_read_tokens,
                          SUM(cache_creation_tokens) AS cache_creation_tokens
                   FROM usage_events
                   WHERE provider = ? AND ts >= ?
                   GROUP BY model
                   ORDER BY (SUM(input_tokens) + SUM(output_tokens)
                             + SUM(cache_read_tokens) + SUM(cache_creation_tokens)) DESC""",
                (provider, start_ts),
            ).fetchall()
        return [
            ModelUsage(
                model=r["model"],
                input_tokens=r["input_tokens"] or 0,
                output_tokens=r["output_tokens"] or 0,
                cache_read_tokens=r["cache_read_tokens"] or 0,
                cache_creation_tokens=r["cache_creation_tokens"] or 0,
            )
            for r in rows
        ]

    def close(self) -> None:
        with self._lock:
            self._conn.close()
