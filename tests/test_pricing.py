from token_counter import pricing
from token_counter.models import ModelUsage


def test_price_for_substring_match():
    assert pricing.price_for("gpt-4o-mini") == (0.15, 0.60)
    assert pricing.price_for("gpt-4o-2024-08-06") == (2.50, 10.0)
    assert pricing.price_for("totally-unknown-model") is None


def test_estimate_cost_known_model():
    # 1M input + 1M output of gpt-4o = $2.50 + $10 = $12.50
    cost = pricing.estimate_cost("gpt-4o", input_tokens=1_000_000, output_tokens=1_000_000)
    assert abs(cost - 12.5) < 1e-6


def test_estimate_cost_unknown_returns_none():
    assert pricing.estimate_cost("mystery", 1000, 1000) is None


def test_cost_for_usage_sums_known_only():
    usages = [
        ModelUsage("gpt-4o", input_tokens=1_000_000, output_tokens=0),  # $2.50
        ModelUsage("unknown-x", input_tokens=1_000_000),                # $0
    ]
    assert abs(pricing.cost_for_usage(usages) - 2.5) < 1e-6


def test_user_override(tmp_path, monkeypatch):
    cfg = tmp_path / ".token_counter"
    cfg.mkdir()
    (cfg / "pricing.json").write_text('{"my-model": {"input": 1, "output": 2}}')
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))  # Windows home
    pricing._table.cache_clear()
    try:
        c = pricing.estimate_cost("my-model", input_tokens=1_000_000, output_tokens=1_000_000)
        assert abs(c - 3.0) < 1e-6
    finally:
        pricing._table.cache_clear()


def test_format_cost():
    assert pricing.format_cost(None) == ""
    assert pricing.format_cost(0) == ""
    assert pricing.format_cost(0.004) == "<$0.01"
    assert pricing.format_cost(4.2) == "$4.20"
