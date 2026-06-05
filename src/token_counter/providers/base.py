"""Provider plugin interface.

A provider reports the current "used / limit / remaining" picture for one
account as a ``ProviderStatus`` (a list of gauges). Add a new provider in three
steps:

1. Subclass ``Provider`` and implement ``poll``.
2. Decorate the class with ``@register("your_type_name")``.
3. Import the module in ``providers/__init__.py`` so the decorator runs.

That's the entire extension surface — config ``type:`` strings map to whatever
you register here.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Callable, Type

from ..config import ProviderConfig
from ..ledger import Ledger
from ..models import ProviderStatus

_REGISTRY: dict[str, Type["Provider"]] = {}


def register(type_name: str) -> Callable[[Type["Provider"]], Type["Provider"]]:
    def decorator(cls: Type["Provider"]) -> Type["Provider"]:
        if type_name in _REGISTRY:
            raise ValueError(f"provider type {type_name!r} already registered")
        _REGISTRY[type_name] = cls
        cls.type_name = type_name
        return cls

    return decorator


def create_provider(config: ProviderConfig, ledger: Ledger, store=None) -> "Provider":
    try:
        cls = _REGISTRY[config.type]
    except KeyError:
        known = ", ".join(sorted(_REGISTRY)) or "(none)"
        raise ValueError(
            f"unknown provider type {config.type!r} for {config.name!r}; known types: {known}"
        )
    return cls(config, ledger, store)


def registered_types() -> list[str]:
    return sorted(_REGISTRY)


class Provider(ABC):
    """Base class for all usage providers."""

    type_name: str = "base"

    #: Which credential kinds the login screen should offer for this provider.
    #: Override in subclasses (e.g. ``("api_key", "oauth")``).
    auth_methods: tuple[str, ...] = ("api_key",)

    def __init__(self, config: ProviderConfig, ledger: Ledger, store=None):
        self.config = config
        self.ledger = ledger
        self.store = store  # optional CredentialStore for remembered keys

    @property
    def name(self) -> str:
        return self.config.name

    def api_key(self) -> str | None:
        """Resolve the API key: config/env first, then the remembered keyring.

        This is what makes sign-in persist — once saved, the key is read from the
        OS keyring on every restart with no retyping or env-var setup.
        """
        key = self.config.secret("api_key")
        if key:
            return key
        if self.store is not None:
            return self.store.get(self.name, "api_key")
        return None

    @abstractmethod
    def poll(self, now: datetime | None = None) -> ProviderStatus:
        """Return the current usage/limit picture.

        Implementations should never raise for expected failures (auth,
        network, no-data-yet) — catch them and return a ``ProviderStatus`` with
        ``error`` set so the tray shows the problem instead of crashing the
        refresh loop.
        """
        raise NotImplementedError

    def validate_credential(self, secret: str) -> tuple[bool, str]:
        """Probe the provider with ``secret`` to confirm it works.

        Used by the login screen's "Validate & Save". Default: accept any
        non-empty value. Override to make a real probe call.
        """
        if secret and secret.strip():
            return True, "saved (not validated)"
        return False, "empty credential"

    @staticmethod
    def _now(now: datetime | None) -> datetime:
        return now or datetime.now(timezone.utc)
