import json
import urllib.error
import urllib.request
from datetime import datetime, timezone

from token_counter.config import ServerConfig
from token_counter.ledger import Ledger
from token_counter.server import UsageServer


def _post(url, payload):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return resp.status, json.loads(resp.read().decode())


def test_server_records_usage(tmp_path):
    ledger = Ledger(tmp_path / "l.db")
    # port 0 lets the OS pick a free port
    server = UsageServer(ServerConfig(host="127.0.0.1", port=0), ledger)
    server.start()
    try:
        base = server.address
        status, body = _post(
            f"{base}/usage",
            {"provider": "claude", "model": "opus", "input_tokens": 100, "output_tokens": 50},
        )
        assert status == 202
        assert body["status"] == "recorded"

        usage = ledger.usage_since("claude", datetime(2026, 6, 1, tzinfo=timezone.utc))
        assert usage[0].total == 150
    finally:
        server.stop()


def test_server_rejects_missing_fields(tmp_path):
    ledger = Ledger(tmp_path / "l.db")
    server = UsageServer(ServerConfig(host="127.0.0.1", port=0), ledger)
    server.start()
    try:
        try:
            _post(f"{server.address}/usage", {"model": "opus"})
            assert False, "expected HTTP 400"
        except urllib.error.HTTPError as exc:
            assert exc.code == 400
    finally:
        server.stop()


def test_server_captures_rate_limit_headers(tmp_path):
    ledger = Ledger(tmp_path / "l.db")
    server = UsageServer(ServerConfig(host="127.0.0.1", port=0), ledger)
    server.start()
    try:
        status, body = _post(
            f"{server.address}/ratelimit",
            {
                "provider": "claude",
                "headers": {
                    "anthropic-ratelimit-tokens-limit": "40000",
                    "anthropic-ratelimit-tokens-remaining": "12000",
                },
            },
        )
        assert status == 202
        assert body["rate_limit_windows"] == 1

        snap = ledger.get_rate_limits("claude")
        assert snap is not None
        _captured_at, windows = snap
        assert windows["tokens"]["limit"] == 40000
        assert windows["tokens"]["remaining"] == 12000
    finally:
        server.stop()


def test_ratelimit_rejects_unrecognized_headers(tmp_path):
    ledger = Ledger(tmp_path / "l.db")
    server = UsageServer(ServerConfig(host="127.0.0.1", port=0), ledger)
    server.start()
    try:
        try:
            _post(f"{server.address}/ratelimit", {"provider": "x", "headers": {"server": "nginx"}})
            assert False, "expected HTTP 400"
        except urllib.error.HTTPError as exc:
            assert exc.code == 400
    finally:
        server.stop()


def test_healthz(tmp_path):
    ledger = Ledger(tmp_path / "l.db")
    server = UsageServer(ServerConfig(host="127.0.0.1", port=0), ledger)
    server.start()
    try:
        with urllib.request.urlopen(f"{server.address}/healthz", timeout=5) as resp:
            assert json.loads(resp.read().decode())["status"] == "ok"
    finally:
        server.stop()
