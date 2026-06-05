"""Helpers for the app re-launching itself (tray -> dashboard/login/popup).

Works both when running from source (``python -m token_counter <cmd>``) and when
frozen into a single ``.exe`` by PyInstaller (``tokn.exe <cmd>``), where
``-m module`` execution isn't available.
"""

from __future__ import annotations

import sys


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def subprocess_args(command: str, config_path: str | None = None) -> list[str]:
    # ``-c`` is a GLOBAL option on the parent parser, so it must come BEFORE the
    # subcommand (argparse rejects it if placed after).
    base = [sys.executable] if is_frozen() else [sys.executable, "-m", "token_counter"]
    opts = ["-c", config_path] if config_path else []
    return base + opts + [command]
