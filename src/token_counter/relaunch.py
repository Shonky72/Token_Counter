"""Helpers for the app re-launching itself (tray -> dashboard/login/popup).

Works both when running from source (``python -m token_counter <cmd>``) and when
frozen into a single ``.exe`` by PyInstaller (``tokn.exe <cmd>``), where
``-m module`` execution isn't available.
"""

from __future__ import annotations

import subprocess
import sys


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def popen_kwargs() -> dict:
    """Extra kwargs so spawned processes never flash a console window on Windows.

    Returns ``{}`` everywhere except Windows, where it sets ``CREATE_NO_WINDOW``
    plus a hidden ``STARTUPINFO``. Use with ``subprocess.run``/``Popen`` for any
    spawn (PowerShell shortcut helpers, relaunching tokn windows, etc.).
    """
    if not sys.platform.startswith("win"):
        return {}
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    kwargs: dict = {"creationflags": flags}
    try:  # belt and braces: also hide via STARTUPINFO
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0  # SW_HIDE
        kwargs["startupinfo"] = si
    except Exception:  # pragma: no cover - non-Windows / odd builds
        pass
    return kwargs



def subprocess_args(command: str, config_path: str | None = None) -> list[str]:
    # ``-c`` is a GLOBAL option on the parent parser, so it must come BEFORE the
    # subcommand (argparse rejects it if placed after).
    base = [sys.executable] if is_frozen() else [sys.executable, "-m", "token_counter"]
    opts = ["-c", config_path] if config_path else []
    return base + opts + [command]
