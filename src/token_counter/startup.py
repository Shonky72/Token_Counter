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
_VALUE_NAME = "tokn"


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


def _registry_enabled() -> bool:
    import winreg

    try:
        with _open_key(write=False) as key:
            winreg.QueryValueEx(key, _VALUE_NAME)
            return True
    except FileNotFoundError:
        return False
    except OSError:
        return False


def is_enabled() -> bool:
    """True if tokn is registered to launch at login by *either* mechanism."""
    if not is_supported():
        return False
    if _registry_enabled():
        return True
    try:
        from .shortcut import startup_shortcut_exists

        return startup_shortcut_exists()
    except Exception:
        return False


def _registry_enable(command: str | None = None) -> bool:
    import winreg

    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
            winreg.SetValueEx(
                key, _VALUE_NAME, 0, winreg.REG_SZ, command or startup_command()
            )
        return True
    except OSError:
        return False


def _registry_disable() -> bool:
    import winreg

    try:
        with _open_key(write=True) as key:
            winreg.DeleteValue(key, _VALUE_NAME)
        return True
    except FileNotFoundError:
        return True
    except OSError:
        return False


def _shortcut_target() -> tuple[str, str]:
    """(target, arguments) for the Startup-folder .lnk."""
    if getattr(sys, "frozen", False):
        return str(Path(sys.executable)), "run"          # bare exe → tray
    exe = Path(sys.executable)
    pythonw = exe.with_name("pythonw.exe")
    runner = pythonw if pythonw.exists() else exe
    return str(runner), "-m token_counter run"


def enable_detailed(command: str | None = None) -> tuple[bool, str]:
    """Register startup via the registry Run key AND the Startup-folder shortcut.

    Returns (ok, human-readable detail) — ok is True if at least one mechanism
    took. The detail names the exact command/path registered (or the failure).
    """
    if not is_supported():
        return False, "startup registration is only available on Windows"
    reg_ok = _registry_enable(command)
    lnk_ok = False
    lnk_info = ""
    try:
        from .shortcut import create_startup_shortcut

        target, args = _shortcut_target()
        lnk_ok, lnk_info = create_startup_shortcut(target=target, arguments=args)
    except Exception as exc:  # pragma: no cover - Windows/COM only
        lnk_info = f"shortcut error: {exc}"
    if reg_ok or lnk_ok:
        cmd = command or startup_command()
        where = []
        if reg_ok:
            where.append("HKCU Run")
        if lnk_ok:
            where.append("Startup folder")
        return True, f"Registered ({', '.join(where)}). Launches: {cmd}"
    return False, f"Could not register startup. {lnk_info}".strip()


def disable_detailed() -> tuple[bool, str]:
    if not is_supported():
        return False, "startup registration is only available on Windows"
    reg_ok = _registry_disable()
    lnk_ok = True
    try:
        from .shortcut import remove_startup_shortcut

        lnk_ok, _ = remove_startup_shortcut()
    except Exception:  # pragma: no cover - Windows/COM only
        lnk_ok = False
    ok = reg_ok and lnk_ok
    return ok, "Removed from startup." if ok else "Could not fully remove startup entry."


def enable(command: str | None = None) -> bool:
    """Register the startup entry. Returns True on success."""
    return enable_detailed(command)[0]


def disable() -> bool:
    """Remove the startup entry. Returns True on success (or if already absent)."""
    return disable_detailed()[0]


def set_enabled(value: bool, command: str | None = None) -> bool:
    return enable(command) if value else disable()


def set_enabled_detailed(value: bool, command: str | None = None) -> tuple[bool, str]:
    return enable_detailed(command) if value else disable_detailed()
