from datetime import datetime, timezone

import pytest

from token_counter.config import (
    Budget,
    ConfigError,
    ensure_config,
    load_config,
    parse_config,
    save_open_on_startup,
)


def test_parse_minimal_config():
    cfg = parse_config(
        {
            "refresh_seconds": 15,
            "providers": [
                {"name": "claude", "type": "local_ledger", "budget": {"limit": 1000000}}
            ],
        }
    )
    assert cfg.refresh_seconds == 15
    assert len(cfg.providers) == 1
    p = cfg.providers[0]
    assert p.name == "claude"
    assert p.budget.limit == 1000000
    assert p.budget.period == "monthly"  # default


def test_duplicate_provider_names_rejected():
    with pytest.raises(ConfigError):
        parse_config(
            {
                "providers": [
                    {"name": "x", "type": "local_ledger"},
                    {"name": "x", "type": "gemini"},
                ]
            }
        )


def test_missing_type_rejected():
    with pytest.raises(ConfigError):
        parse_config({"providers": [{"name": "x"}]})


def test_invalid_period_rejected():
    with pytest.raises(ConfigError):
        Budget(period="hourly")


def test_secret_resolution_from_env(monkeypatch):
    cfg = parse_config(
        {
            "providers": [
                {
                    "name": "claude",
                    "type": "anthropic_admin",
                    "admin_key_env": "MY_ADMIN_KEY",
                }
            ]
        }
    )
    monkeypatch.setenv("MY_ADMIN_KEY", "sk-ant-admin-abc")
    assert cfg.providers[0].secret("admin_key") == "sk-ant-admin-abc"


def test_inline_secret_takes_precedence():
    cfg = parse_config(
        {"providers": [{"name": "c", "type": "anthropic_admin", "admin_key": "inline"}]}
    )
    assert cfg.providers[0].secret("admin_key") == "inline"


@pytest.mark.parametrize(
    "period,expected",
    [
        ("daily", datetime(2026, 6, 4, 0, 0, tzinfo=timezone.utc)),
        ("monthly", datetime(2026, 6, 1, 0, 0, tzinfo=timezone.utc)),
        # 2026-06-04 is a Thursday; Monday of that week is 2026-06-01.
        ("weekly", datetime(2026, 6, 1, 0, 0, tzinfo=timezone.utc)),
    ],
)
def test_window_start(period, expected):
    now = datetime(2026, 6, 4, 13, 30, tzinfo=timezone.utc)
    assert Budget(period=period).window_start(now) == expected


def test_total_period_window_is_epoch():
    start = Budget(period="total").window_start(datetime.now(timezone.utc))
    assert start.year == 1970


def test_startup_and_view_mode_defaults_and_parsing():
    cfg = parse_config({"providers": []})
    assert cfg.open_on_startup is False
    assert cfg.view_mode == "dashboard"
    cfg2 = parse_config({"open_on_startup": True, "view_mode": "compact", "providers": []})
    assert cfg2.open_on_startup is True
    assert cfg2.view_mode == "compact"


def test_ensure_config_creates_valid_default(tmp_path):
    path = tmp_path / "nested" / "config.yaml"
    assert not path.exists()
    ensure_config(path)
    assert path.exists()
    # The default starts empty — services are added from the login window.
    cfg = load_config(path)
    assert cfg.providers == []


def test_add_and_remove_provider_roundtrip(tmp_path):
    from token_counter.config import add_provider, remove_provider

    path = tmp_path / "config.yaml"
    ensure_config(path)
    add_provider(path, "claude")
    add_provider(path, "openai")
    names = [p.name for p in load_config(path).providers]
    assert names == ["claude", "openai"]
    # The catalog template carries display options through.
    claude = next(p for p in load_config(path).providers if p.name == "claude")
    assert claude.type == "rate_limit"
    assert claude.option("scheme") == "anthropic"

    remove_provider(path, "claude")
    assert [p.name for p in load_config(path).providers] == ["openai"]


def test_add_provider_multiple_keys_per_service(tmp_path):
    from token_counter.config import add_provider, remove_provider

    path = tmp_path / "config.yaml"
    ensure_config(path)
    n1 = add_provider(path, "claude", label="Work")
    n2 = add_provider(path, "claude", label="Home")
    assert (n1, n2) == ("claude", "claude-2")

    providers = load_config(path).providers
    by_name = {p.name: p for p in providers}
    # Both record the catalog service id and carry distinct labels.
    assert by_name["claude"].option("service") == "claude"
    assert by_name["claude-2"].option("service") == "claude"
    assert by_name["claude"].option("display_name") == "Claude — Work"
    assert by_name["claude-2"].option("display_name") == "Claude — Home"

    # Removing one instance leaves the other intact.
    remove_provider(path, "claude")
    assert [p.name for p in load_config(path).providers] == ["claude-2"]


def test_group_by_service_keeps_instances_adjacent():
    from token_counter.config import group_by_service

    class P:
        def __init__(self, name, service):
            self._name, self._service = name, service

        @property
        def name(self):
            return self._name

        def option(self, key, default=None):
            return {"service": self._service}.get(key, default)

    claude = P("claude", "claude")
    gemini = P("gemini", "gemini")
    claude2 = P("claude-2", "claude")
    ordered = group_by_service([claude, gemini, claude2])
    assert [p.name for p in ordered] == ["claude", "claude-2", "gemini"]


def test_ensure_config_does_not_overwrite(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("refresh_seconds: 99\nproviders: []\n", encoding="utf-8")
    ensure_config(path)
    assert load_config(path).refresh_seconds == 99


def test_save_open_on_startup_roundtrip(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("refresh_seconds: 30\nproviders: []\n", encoding="utf-8")
    save_open_on_startup(path, True)
    cfg = load_config(path)
    assert cfg.open_on_startup is True
    assert cfg.refresh_seconds == 30  # other keys preserved
    save_open_on_startup(path, False)
    assert load_config(path).open_on_startup is False
