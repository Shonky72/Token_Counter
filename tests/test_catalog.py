from token_counter import catalog
from token_counter.config import parse_config


def test_big_three_present():
    assert set(catalog.service_keys()) == {"claude", "openai", "gemini"}


def test_provider_config_parses():
    for key in catalog.service_keys():
        cfg = parse_config({"providers": [catalog.provider_config_for(key)]})
        pc = cfg.providers[0]
        assert pc.name == key
        svc = catalog.get(key)
        assert pc.type == svc.type
        assert pc.option("display_name") == svc.display_name


def test_services_have_help_and_url():
    for key in catalog.service_keys():
        svc = catalog.get(key)
        assert svc.key_url.startswith("https://")
        assert svc.help.strip()


def test_unknown_service_raises():
    import pytest

    with pytest.raises(KeyError):
        catalog.provider_config_for("nope")
