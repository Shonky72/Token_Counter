from datetime import datetime, timezone

from token_counter import probe
from token_counter.config import parse_config
from token_counter.ledger import Ledger
from token_counter.providers import create_provider

_ANTHROPIC_HEADERS = {
    "anthropic-ratelimit-tokens-limit": "40000",
    "anthropic-ratelimit-tokens-remaining": "39990",
    "anthropic-ratelimit-requests-limit": "50",
    "anthropic-ratelimit-requests-remaining": "49",
}


def test_fetch_rate_limits_anthropic(monkeypatch):
    captured = {}

    def fake_request(url, headers, data=None):
        captured["url"] = url
        captured["data"] = data
        return True, "ok", _ANTHROPIC_HEADERS

    monkeypatch.setattr(probe, "_request", fake_request)
    ok, _msg, headers = probe.fetch_rate_limits("anthropic", "sk-ant-x")
    assert ok
    assert "messages" in captured["url"]
    assert captured["data"]  # a real POST body
    assert headers["anthropic-ratelimit-tokens-limit"] == "40000"


def test_fetch_rate_limits_gemini_unsupported():
    ok, msg, headers = probe.fetch_rate_limits("google", "key")
    assert ok is False
    assert headers == {}


def test_validate_credential_populates_gauge(monkeypatch, tmp_path):
    # Both the cheap probe and the live fetch are stubbed (no network).
    monkeypatch.setattr(probe, "probe", lambda scheme, key: (True, "ok", {}))
    monkeypatch.setattr(
        probe, "fetch_rate_limits",
        lambda scheme, key: (True, "ok", _ANTHROPIC_HEADERS),
    )
    cfg = parse_config(
        {"providers": [{"name": "claude", "type": "rate_limit", "scheme": "anthropic"}]}
    )
    ledger = Ledger(tmp_path / "l.db")
    provider = create_provider(cfg.providers[0], ledger)

    ok, msg = provider.validate_credential("sk-ant-x")
    assert ok and "live limits" in msg

    status = provider.poll(datetime.now(timezone.utc))
    assert status.error is None
    labels = {g.label for g in status.gauges}
    assert "tokens/min" in labels
