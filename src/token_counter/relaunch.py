"""Helpers for the app re-launching itself (tray -> dashboard/login/popup).

Works both when running from source (``python -m token_counter <cmd>``) and when
frozen into a single ``.exe`` by PyInstaller (``TokenCounter.exe <cmd>``), where
``-m module`` execution isn't available.
"""

from __future__ import annotations

import sys


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def subprocess_args(command: str, config_path: str | None = None) -> list[str]:
    if is_frozen():
        args = [sys.executable, command]
    else:
        args = [sys.executable, "-m", "token_counter", command]
    if config_path:
        args += ["-c", config_path]
    return args
