"""Create a Windows Desktop shortcut to Token Counter.

Uses PowerShell's WScript.Shell COM object, so there's no extra dependency. On
non-Windows platforms it's a no-op that reports it isn't supported.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _startup_dir() -> Path | None:
    """The user's Startup folder, where a login-launch .lnk lives."""
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return None
    return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def is_supported() -> bool:
    return sys.platform.startswith("win")


def _ps_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def create_desktop_shortcut(
    target: str | None = None,
    arguments: str = "",
    name: str = "tokn",
    icon: str | None = None,
) -> tuple[bool, str]:
    """Create ``<Desktop>/<name>.lnk``. Returns (ok, path-or-message)."""
    if not is_supported():
        return False, "desktop shortcuts are only supported on Windows"

    target = target or sys.executable
    icon = icon or target  # the frozen .exe carries its own icon
    lnk = "[IO.Path]::Combine([Environment]::GetFolderPath('Desktop')," + _ps_quote(f"{name}.lnk") + ")"
    script = (
        "$ws = New-Object -ComObject WScript.Shell; "
        f"$s = $ws.CreateShortcut({lnk}); "
        f"$s.TargetPath = {_ps_quote(target)}; "
        f"$s.Arguments = {_ps_quote(arguments)}; "
        f"$s.WorkingDirectory = {_ps_quote(str(Path(target).parent))}; "
        f"$s.IconLocation = {_ps_quote(icon)}; "
        "$s.Save(); "
        "Write-Output $s.FullName"
    )
    return _run_ps(script, "shortcut creation failed")


def create_startup_shortcut(
    target: str | None = None,
    arguments: str = "run",
    name: str = "tokn",
    icon: str | None = None,
) -> tuple[bool, str]:
    """Create ``<Startup>/<name>.lnk`` so the app launches at login.

    The Startup special folder is the most reliable, user-visible autostart
    mechanism (it shows up in Task Manager → Startup). Returns (ok, path-or-msg).
    """
    if not is_supported():
        return False, "startup shortcuts are only supported on Windows"
    target = target or sys.executable
    icon = icon or target
    lnk = ("[IO.Path]::Combine([Environment]::GetFolderPath('Startup'),"
           + _ps_quote(f"{name}.lnk") + ")")
    script = (
        "$ws = New-Object -ComObject WScript.Shell; "
        f"$s = $ws.CreateShortcut({lnk}); "
        f"$s.TargetPath = {_ps_quote(target)}; "
        f"$s.Arguments = {_ps_quote(arguments)}; "
        f"$s.WorkingDirectory = {_ps_quote(str(Path(target).parent))}; "
        f"$s.IconLocation = {_ps_quote(icon)}; "
        "$s.Save(); "
        "Write-Output $s.FullName"
    )
    return _run_ps(script, "startup shortcut creation failed")


def remove_startup_shortcut(name: str = "tokn") -> tuple[bool, str]:
    """Delete ``<Startup>/<name>.lnk`` if present. Returns (ok, message).

    Pure filesystem (no PowerShell) so it never spawns a process / flashes a
    console — important because the tray polls startup state.
    """
    if not is_supported():
        return False, "startup shortcuts are only supported on Windows"
    d = _startup_dir()
    if d is None:
        return False, "could not locate the Startup folder"
    lnk = d / f"{name}.lnk"
    try:
        existed = lnk.exists()
        lnk.unlink(missing_ok=True)
        return True, "removed" if existed else "absent"
    except OSError as exc:
        return False, f"could not remove startup shortcut: {exc}"


def startup_shortcut_exists(name: str = "tokn") -> bool:
    """True if ``<Startup>/<name>.lnk`` is present.

    A plain file check — no subprocess — so calling it on a timer is cheap and
    never flashes a console window.
    """
    if not is_supported():
        return False
    d = _startup_dir()
    return bool(d and (d / f"{name}.lnk").exists())


def remove_desktop_shortcut(name: str = "tokn") -> tuple[bool, str]:
    """Delete ``<Desktop>/<name>.lnk`` if present. Returns (ok, message)."""
    if not is_supported():
        return False, "desktop shortcuts are only supported on Windows"
    lnk = "[IO.Path]::Combine([Environment]::GetFolderPath('Desktop')," + _ps_quote(f"{name}.lnk") + ")"
    script = (
        f"$p = {lnk}; "
        "if (Test-Path $p) { Remove-Item $p -Force; Write-Output 'removed' } "
        "else { Write-Output 'absent' }"
    )
    return _run_ps(script, "shortcut removal failed")


def _run_ps(script: str, fail_msg: str) -> tuple[bool, str]:
    from .relaunch import popen_kwargs

    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, timeout=30, **popen_kwargs(),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"could not run PowerShell: {exc}"
    if result.returncode != 0:
        return False, result.stderr.strip() or fail_msg
    return True, result.stdout.strip() or "ok"
