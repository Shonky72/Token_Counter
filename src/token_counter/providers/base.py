"""Provider plugin interface.

A provider knows how to report *current usage for the active budget window* for
one account. Add a new provider in three steps:

1. Subclass ``Provider`` and implement ``get_usage``.
2. Decorate the class with ``@register("your_type_name")``.
3. Import the module in ``providers/__init__.py`` so the decorator runs.

That's the entire extension surface — config ``type:`` strings map to whatever
you register here.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Callable, Type

from ..config import ProviderConfig
from ..ledger import Ledger
from ..models import ProviderUsage

_REGISTRY: dict[str, Type["Provider"]] = {}


def register(type_name: str) -> Callable[[Type["Provider"]], Type["Provider"]]:
    def decorator(cls: Type["Provider"]) -> Type["Provider"]:
        if type_name in _REGISTRY:
            raise ValueError(f"provider type {type_name!r} already registered")
        _REGISTRY[type_name] = cls
        cls.type_name = type_name
        return cls

    return decorator


def create_provider(config: ProviderConfig, ledger: Ledger) -> "Provider":
    try:
        cls = _REGISTRY[config.type]
    except KeyError:
        known = ", ".join(sorted(_REGISTRY)) or "(none)"
        raise ValueError(
            f"unknown provider type {config.type!r} for {config.name!r}; known types: {known}"
        )
    return cls(config, ledger)


def registered_types() -> list[str]:
    return sorted(_REGISTRY)


class Provider(ABC):
    """Base class for all usage providers."""

    type_name: str = "base"

    def __init__(self, config: ProviderConfig, ledger: Ledger):
        self.config = config
        self.ledger = ledger

    @property
    def name(self) -> str:
        return self.config.name

    @abstractmethod
    def get_usage(self, window_start: datetime) -> ProviderUsage:
        """Return token usage for this provider since ``window_start`` (UTC).

        Implementations should never raise for expected failures (auth,
        network) — catch them and return a ``ProviderUsage`` with ``error`` set
        so the tray can show the problem instead of crashing the refresh loop.
        """
        raise NotImplementedError
