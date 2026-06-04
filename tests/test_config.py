from datetime import datetime, timezone

import pytest

from token_counter.config import Budget, ConfigError, parse_config


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
