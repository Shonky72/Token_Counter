"""Clean uninstall: remove the startup entry, Desktop shortcut, and saved keys.

This undoes everything the app wrote *outside* its own folder, so a user can
fully back out. With ``purge=True`` it also deletes the config/ledger/logos
directory. It never touches the program files themselves (the .exe or source).
"""

from __future__ import annotations

import shutil
from pathlib import Path

from .auth import CredentialStore

DATA_DIR = Path("~/.token_counter").expanduser()
_DEFAULT_PROVIDERS = ("claude", "openai", "gemini")


def _provider_names(config_path: str | None) -> list[str]:
    """Best-effort list of provider names whose keys we should clear."""
    names: set[str] = set(_DEFAULT_PROVIDERS)
    if config_path:
        try:
            from .config import load_config

            for p in load_config(config_path).providers:
                names.add(p.name)
        except Exception:
            pass
    return sorted(names)


def uninstall(
    remove_keys: bool = True,
    purge: bool = False,
    config_path: str | None = None,
    store: CredentialStore | None = None,
) -> list[str]:
    """Perform the uninstall steps and return a list of human-readable results."""
    results: list[str] = []

    from . import startup as startup_mod

    if startup_mod.is_supported():
        ok = startup_mod.disable()
        results.append("startup entry removed" if ok else "could not remove startup entry")
    else:
        results.append("startup entry: nothing to do (not Windows)")

    from .shortcut import is_supported as shortcut_supported, remove_desktop_shortcut

    if shortcut_supported():
        ok, msg = remove_desktop_shortcut()
        results.append(f"desktop shortcut: {msg}")
    else:
        results.append("desktop shortcut: nothing to do (not Windows)")

    if remove_keys:
        store = store or CredentialStore()
        cleared = 0
        for name in _provider_names(config_path):
            for kind in ("api_key", "oauth"):
                if store.get(name, kind):
                    store.delete(name, kind)
                    cleared += 1
        results.append(f"removed {cleared} saved credential(s)")

    if purge:
        if DATA_DIR.exists():
            shutil.rmtree(DATA_DIR, ignore_errors=True)
            results.append(f"deleted data folder {DATA_DIR}")
        else:
            results.append("data folder already gone")

    return results
