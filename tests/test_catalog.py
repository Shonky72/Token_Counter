from token_counter import catalog
from token_counter.config import parse_config


def test_big_three_and_more():
    keys = set(catalog.service_keys())
    assert {"claude", "openai", "gemini"} <= keys
    assert len(keys) >= 10  # full list, not just the big three


def test_provider_config_parses():
    for key in catalog.service_keys():
        cfg = parse_config({"providers": [catalog.provider_config_for(key)]})
        pc = cfg.providers[0]
        assert pc.name == key
        svc = catalog.get(key)
        assert pc.type == svc.type
        assert pc.option("display_name") == svc.display_name


def test_openai_compatible_have_base_url_and_model():
    for key in catalog.service_keys():
        svc = catalog.get(key)
        if svc.scheme == "openai" or key == "claude":
            assert svc.base_url and svc.base_url.startswith("https://")
            assert svc.test_model


def test_services_have_help_and_url():
    for key in catalog.service_keys():
        svc = catalog.get(key)
        assert svc.key_url.startswith("https://")
        assert svc.help.strip()


def test_every_service_has_usage_url():
    for key in catalog.service_keys():
        svc = catalog.get(key)
        assert svc.usage_url and svc.usage_url.startswith("https://")
        assert catalog.provider_config_for(key)["usage_url"] == svc.usage_url


def test_claude_usage_is_admin_pull_provider():
    # The "Claude — Usage" account pulls cumulative tokens from the Anthropic
    # Usage/Admin API (vs the rate-limit-header "claude" card).
    svc = catalog.get("claude_usage")
    assert svc is not None
    assert svc.type == "anthropic_admin"
    cfg = parse_config({"providers": [catalog.provider_config_for("claude_usage")]})
    pc = cfg.providers[0]
    assert pc.type == "anthropic_admin"
    assert pc.budget.period == "monthly"  # gives the ring a denominator


def test_claude_tracked_is_ledger_backed():
    # The no-key "Claude — Tracked" card renders imported/reported usage.
    svc = catalog.get("claude_tracked")
    assert svc is not None and svc.type == "local_ledger"
    cfg = parse_config({"providers": [catalog.provider_config_for("claude_tracked")]})
    assert cfg.providers[0].budget.period == "monthly"


def test_unknown_service_raises():
    import pytest

    with pytest.raises(KeyError):
        catalog.provider_config_for("nope")
