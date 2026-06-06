"""Tiny persistent UI state (e.g. remembered window positions).

A flat JSON file at ``~/.token_counter/state.json``. Best-effort: any read/write
failure degrades to an in-memory default so the UI never breaks.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

STATE_PATH = Path("~/.token_counter/state.json").expanduser()


def _read() -> dict:
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def get(key: str, default: Any = None) -> Any:
    return _read().get(key, default)


def set(key: str, value: Any) -> None:  # noqa: A001 - small deliberate API
    data = _read()
    data[key] = value
    try:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        STATE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass
