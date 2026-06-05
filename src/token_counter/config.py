"""Configuration loading and budget-period maths.

Config is YAML (see ``config.example.yaml``). Everything is validated up front
so a typo surfaces at startup, not three hours into a session.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:  # PyYAML is the only config dependency; degrade to JSON if missing.
    import yaml
except ImportError:  # pragma: no cover - exercised only without PyYAML
    yaml = None

import json

VALID_PERIODS = {"daily", "weekly", "monthly", "total"}
DEFAULT_REFRESH_SECONDS = 30


class ConfigError(Exception):
    """Raised for any malformed configuration."""


@dataclass
class Budget:
    period: str = "monthly"
    limit: int | None = None
    per_model: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.period not in VALID_PERIODS:
            raise ConfigError(
                f"budget.period must be one of {sorted(VALID_PERIODS)}, got {self.period!r}"
            )
        if self.limit is not None and self.limit < 0:
            raise ConfigError("budget.limit must be >= 0")

    def window_start(self, now: datetime | None = None) -> datetime:
        """Start of the current budget window, in UTC.

        Ledger timestamps are stored in UTC, so windows are computed in UTC too.
        """
        now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        if self.period == "daily":
            return now.replace(hour=0, minute=0, second=0, microsecond=0)
        if self.period == "weekly":
            monday = now - timedelta(days=now.weekday())
            return monday.replace(hour=0, minute=0, second=0, microsecond=0)
        if self.period == "monthly":
            return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        # total
        return datetime(1970, 1, 1, tzinfo=timezone.utc)


@dataclass
class ProviderConfig:
    name: str
    type: str
    options: dict[str, Any] = field(default_factory=dict)
    budget: Budget = field(default_factory=Budget)

    def option(self, key: str, default: Any = None) -> Any:
        return self.options.get(key, default)

    def secret(self, key: str) -> str | None:
        """Resolve a secret from ``<key>`` or ``<key>_env`` (env var name)."""
        if key in self.options and self.options[key]:
            return str(self.options[key])
        env_name = self.options.get(f"{key}_env")
        if env_name:
            return os.environ.get(str(env_name))
        return None


@dataclass
class ServerConfig:
    enabled: bool = True
    host: str = "127.0.0.1"
    port: int = 8787


@dataclass
class AppConfig:
    refresh_seconds: int = DEFAULT_REFRESH_SECONDS
    ledger_path: str = "~/.token_counter/ledger.db"
    open_on_startup: bool = False
    view_mode: str = "dashboard"  # "dashboard" | "compact"
    server: ServerConfig = field(default_factory=ServerConfig)
    providers: list[ProviderConfig] = field(default_factory=list)

    @property
    def resolved_ledger_path(self) -> Path:
        return Path(self.ledger_path).expanduser()


def _parse_budget(raw: dict[str, Any] | None) -> Budget:
    raw = raw or {}
    if not isinstance(raw, dict):
        raise ConfigError("budget must be a mapping")
    per_model = raw.get("per_model") or {}
    if not isinstance(per_model, dict):
        raise ConfigError("budget.per_model must be a mapping of model -> limit")
    return Budget(
        period=raw.get("period", "monthly"),
        limit=raw.get("limit"),
        per_model={str(k): int(v) for k, v in per_model.items()},
    )


def _parse_provider(raw: dict[str, Any]) -> ProviderConfig:
    if not isinstance(raw, dict):
        raise ConfigError("each provider must be a mapping")
    if "name" not in raw:
        raise ConfigError("provider is missing required field 'name'")
    if "type" not in raw:
        raise ConfigError(f"provider {raw['name']!r} is missing required field 'type'")
    reserved = {"name", "type", "budget"}
    options = {k: v for k, v in raw.items() if k not in reserved}
    return ProviderConfig(
        name=str(raw["name"]),
        type=str(raw["type"]),
        options=options,
        budget=_parse_budget(raw.get("budget")),
    )


def parse_config(raw: dict[str, Any]) -> AppConfig:
    if not isinstance(raw, dict):
        raise ConfigError("top-level config must be a mapping")

    server_raw = raw.get("server") or {}
    server = ServerConfig(
        enabled=bool(server_raw.get("enabled", True)),
        host=str(server_raw.get("host", "127.0.0.1")),
        port=int(server_raw.get("port", 8787)),
    )

    providers_raw = raw.get("providers") or []
    if not isinstance(providers_raw, list):
        raise ConfigError("'providers' must be a list")
    providers = [_parse_provider(p) for p in providers_raw]

    names = [p.name for p in providers]
    if len(names) != len(set(names)):
        raise ConfigError("provider names must be unique")

    return AppConfig(
        refresh_seconds=int(raw.get("refresh_seconds", DEFAULT_REFRESH_SECONDS)),
        ledger_path=str(raw.get("ledger_path", "~/.token_counter/ledger.db")),
        open_on_startup=bool(raw.get("open_on_startup", False)),
        view_mode=str(raw.get("view_mode", "dashboard")),
        server=server,
        providers=providers,
    )


def save_open_on_startup(path: str | Path, value: bool) -> None:
    """Persist just the ``open_on_startup`` flag back to a YAML/JSON config.

    Keeps the rest of the file intact when toggled from the UI.
    """
    path = Path(path).expanduser()
    raw: dict[str, Any] = {}
    if path.exists():
        text = path.read_text(encoding="utf-8")
        if path.suffix in {".yaml", ".yml"} and yaml is not None:
            raw = yaml.safe_load(text) or {}
        elif path.suffix not in {".yaml", ".yml"}:
            raw = json.loads(text or "{}")
    raw["open_on_startup"] = bool(value)
    if path.suffix in {".yaml", ".yml"}:
        if yaml is None:
            raise ConfigError("PyYAML required to write YAML config")
        path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    else:
        path.write_text(json.dumps(raw, indent=2), encoding="utf-8")


def load_config(path: str | Path) -> AppConfig:
    path = Path(path).expanduser()
    if not path.exists():
        raise ConfigError(f"config file not found: {path}")
    text = path.read_text(encoding="utf-8")
    if path.suffix in {".yaml", ".yml"}:
        if yaml is None:
            raise ConfigError(
                "PyYAML is required to read YAML config; install it or use a .json config"
            )
        raw = yaml.safe_load(text) or {}
    else:
        raw = json.loads(text)
    return parse_config(raw)
