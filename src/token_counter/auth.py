"""Secure-ish credential storage for provider API keys / OAuth tokens.

Prefers the OS keyring (Windows Credential Manager via the ``keyring`` package).
If ``keyring`` isn't installed, falls back to a local JSON file with
owner-only permissions — convenient, but NOT encrypted, so install ``keyring``
for real protection (it's a declared dependency).

Credentials are stored per ``(provider_name, kind)`` where ``kind`` is
``api_key`` or ``oauth`` (the OAuth value is a JSON token bundle).
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

_SERVICE = "token_counter"

try:
    import keyring  # type: ignore

    _HAVE_KEYRING = True
except Exception:  # pragma: no cover - environment dependent
    keyring = None
    _HAVE_KEYRING = False


def _entry(provider: str, kind: str) -> str:
    return f"{provider}:{kind}"


class CredentialStore:
    def __init__(self, fallback_path: str | Path = "~/.token_counter/credentials.json"):
        self.fallback_path = Path(fallback_path).expanduser()

    @property
    def backend(self) -> str:
        return "keyring" if _HAVE_KEYRING else "local-file"

    # --- file fallback -------------------------------------------------
    def _read_file(self) -> dict:
        if not self.fallback_path.exists():
            return {}
        try:
            return json.loads(self.fallback_path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            return {}

    def _write_file(self, data: dict) -> None:
        self.fallback_path.parent.mkdir(parents=True, exist_ok=True)
        self.fallback_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        try:  # best-effort owner-only perms (POSIX)
            os.chmod(self.fallback_path, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:  # pragma: no cover - Windows / unsupported
            pass

    # --- public API ----------------------------------------------------
    def set(self, provider: str, value: str, kind: str = "api_key") -> None:
        if _HAVE_KEYRING:
            keyring.set_password(_SERVICE, _entry(provider, kind), value)
        else:
            data = self._read_file()
            data[_entry(provider, kind)] = value
            self._write_file(data)

    def get(self, provider: str, kind: str = "api_key") -> str | None:
        if _HAVE_KEYRING:
            return keyring.get_password(_SERVICE, _entry(provider, kind))
        return self._read_file().get(_entry(provider, kind))

    def delete(self, provider: str, kind: str = "api_key") -> None:
        if _HAVE_KEYRING:
            try:
                keyring.delete_password(_SERVICE, _entry(provider, kind))
            except Exception:  # pragma: no cover - keyring raises if absent
                pass
        else:
            data = self._read_file()
            data.pop(_entry(provider, kind), None)
            self._write_file(data)

    def has_any(self, provider: str) -> bool:
        return any(self.get(provider, kind) for kind in ("api_key", "oauth"))


def load_credentials_into_env(store: CredentialStore, providers) -> None:
    """Export each provider's stored api_key to the env var its config expects.

    A provider config can say ``api_key_env: ANTHROPIC_API_KEY``; this populates
    that variable from the keyring at startup so providers/probes can read it
    without the key ever living in a file.
    """
    for pc in providers:
        key = store.get(pc.name, "api_key")
        if not key:
            continue
        env_name = pc.options.get("api_key_env")
        if env_name:
            os.environ.setdefault(str(env_name), key)
