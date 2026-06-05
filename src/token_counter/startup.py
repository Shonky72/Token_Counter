"""Manage "launch Token Counter when Windows starts".

Implemented with the per-user registry Run key
(``HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run``), which needs no
admin rights and is the standard place for user startup apps. On non-Windows
platforms the functions degrade to no-ops and ``is_supported()`` returns False,
so the rest of the app (and tests) run anywhere.

The registered command launches the tray with ``pythonw`` (no console window).
"""

from __future__ import annotations

import sys
from pathlib import Path

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_VALUE_NAME = "TokenCounter"


def is_supported() -> bool:
    return sys.platform.startswith("win")


def startup_command() -> str:
    """The command Windows should run at login (quoted, no console window)."""
    # Frozen single-exe: just launch the exe itself.
    if getattr(sys, "frozen", False):
        return f'"{Path(sys.executable)}"'
    exe = Path(sys.executable)
    # Prefer pythonw.exe so no console flashes on login.
    pythonw = exe.with_name("pythonw.exe")
    runner = pythonw if pythonw.exists() else exe
    return f'"{runner}" -m token_counter run'


def _open_key(write: bool):
    import winreg

    access = winreg.KEY_WRITE if write else winreg.KEY_READ
    return winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, access)


def is_enabled() -> bool:
    if not is_supported():
        return False
    import winreg

    try:
        with _open_key(write=False) as key:
            winreg.QueryValueEx(key, _VALUE_NAME)
            return True
    except FileNotFoundError:
        return False
    except OSError:
        return False


def enable(command: str | None = None) -> bool:
    """Register the startup entry. Returns True on success."""
    if not is_supported():
        return False
    import winreg

    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
            winreg.SetValueEx(
                key, _VALUE_NAME, 0, winreg.REG_SZ, command or startup_command()
            )
        return True
    except OSError:
        return False


def disable() -> bool:
    """Remove the startup entry. Returns True on success (or if already absent)."""
    if not is_supported():
        return False
    import winreg

    try:
        with _open_key(write=True) as key:
            winreg.DeleteValue(key, _VALUE_NAME)
        return True
    except FileNotFoundError:
        return True
    except OSError:
        return False


def set_enabled(value: bool, command: str | None = None) -> bool:
    return enable(command) if value else disable()
