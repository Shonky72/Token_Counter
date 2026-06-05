"""The login screen — a Tkinter window for signing into providers.

Two ways to authenticate per provider (as requested, "both"):
  * **API key** — paste it, "Validate & Save" probes the provider live and
    stores it in the OS keyring.
  * **OAuth** — "Sign in" opens your browser (for providers that support it and
    have an ``oauth`` block in config).

Tkinter ships with Python; this window runs on the main thread (launched via
``token-counter login``), so it doesn't fight the pystray event loop.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

from .auth import CredentialStore
from .config import AppConfig, ProviderConfig, load_config
from .ledger import Ledger
from .oauth import GOOGLE_PRESET, OAuthClient
from .providers import create_provider


def _oauth_client_from_config(pc: ProviderConfig) -> OAuthClient | None:
    raw = pc.options.get("oauth")
    if not isinstance(raw, dict):
        return None
    preset = GOOGLE_PRESET if raw.get("preset") == "google" else {}
    client_id = raw.get("client_id") or pc.secret("oauth_client_id")
    if not client_id:
        return None
    return OAuthClient(
        name=pc.name,
        authorization_endpoint=raw.get("authorization_endpoint")
        or preset.get("authorization_endpoint", ""),
        token_endpoint=raw.get("token_endpoint") or preset.get("token_endpoint", ""),
        client_id=str(client_id),
        client_secret=raw.get("client_secret"),
        scopes=raw.get("scopes") or preset.get("scopes", []),
        redirect_port=int(raw.get("redirect_port", 8799)),
    )


class LoginWindow:
    def __init__(self, config: AppConfig, store: CredentialStore, ledger: Ledger):
        import tkinter as tk
        from tkinter import ttk

        self.tk = tk
        self.config = config
        self.store = store
        self.ledger = ledger

        self.root = tk.Tk()
        self.root.title("Token Counter — Accounts")
        self.root.geometry("560x140")
        self.root.minsize(480, 120)

        intro = ttk.Label(
            self.root,
            text=f"Sign in to your AI providers. Credentials are stored via: {store.backend}.",
            padding=(10, 8),
        )
        intro.pack(fill="x")

        body = ttk.Frame(self.root, padding=10)
        body.pack(fill="both", expand=True)

        if not config.providers:
            ttk.Label(body, text="No providers configured. Edit your config.yaml.").pack()

        self._status_vars: dict[str, "tk.StringVar"] = {}
        self._entries: dict[str, "tk.Entry"] = {}

        for pc in config.providers:
            self._build_provider_row(body, pc)

    def _build_provider_row(self, parent, pc: ProviderConfig) -> None:
        tk, ttk = self.tk, __import__("tkinter.ttk", fromlist=["ttk"])
        provider = create_provider(pc, self.ledger, self.store)

        frame = ttk.LabelFrame(parent, text=f"{pc.name}  ({pc.type})", padding=8)
        frame.pack(fill="x", pady=6)

        status = tk.StringVar(value=self._initial_status(pc))
        self._status_vars[pc.name] = status

        if "api_key" in provider.auth_methods:
            row = ttk.Frame(frame)
            row.pack(fill="x")
            ttk.Label(row, text="API key:").pack(side="left")
            entry = ttk.Entry(row, show="*", width=44)
            existing = self.store.get(pc.name, "api_key")
            if existing:
                entry.insert(0, existing)
            entry.pack(side="left", padx=6)
            self._entries[pc.name] = entry
            ttk.Button(
                row, text="Validate & Save", command=lambda p=pc: self._save_key(p)
            ).pack(side="left")
            ttk.Button(
                row, text="Remove", command=lambda p=pc: self._remove(p)
            ).pack(side="left", padx=4)

        oauth_client = _oauth_client_from_config(pc)
        if "oauth" in provider.auth_methods and oauth_client is not None:
            ttk.Button(
                frame, text="Sign in with OAuth", command=lambda p=pc, c=oauth_client: self._oauth(p, c)
            ).pack(anchor="w", pady=(6, 0))

        ttk.Label(frame, textvariable=status, foreground="#555").pack(anchor="w", pady=(4, 0))

    def _initial_status(self, pc: ProviderConfig) -> str:
        if self.store.get(pc.name, "oauth"):
            return "✓ OAuth token stored"
        if self.store.get(pc.name, "api_key"):
            return "✓ API key stored"
        return "not signed in"

    def _set_status(self, name: str, text: str) -> None:
        self._status_vars[name].set(text)

    def _save_key(self, pc: ProviderConfig) -> None:
        secret = self._entries[pc.name].get().strip()
        if not secret:
            self._set_status(pc.name, "✗ enter an API key first")
            return
        self._set_status(pc.name, "validating…")
        self.root.update_idletasks()

        def work():
            provider = create_provider(pc, self.ledger, self.store)
            ok, msg = provider.validate_credential(secret)
            if ok:
                self.store.set(pc.name, secret, "api_key")
            self.root.after(0, lambda: self._set_status(pc.name, ("✓ " if ok else "✗ ") + msg))

        threading.Thread(target=work, daemon=True).start()

    def _remove(self, pc: ProviderConfig) -> None:
        self.store.delete(pc.name, "api_key")
        self.store.delete(pc.name, "oauth")
        if pc.name in self._entries:
            self._entries[pc.name].delete(0, "end")
        self._set_status(pc.name, "removed")

    def _oauth(self, pc: ProviderConfig, client: OAuthClient) -> None:
        from .oauth import run_loopback_flow

        self._set_status(pc.name, "opening browser…")

        def work():
            try:
                tokens = run_loopback_flow(client)
                self.store.set(pc.name, json.dumps(tokens), "oauth")
                self.root.after(0, lambda: self._set_status(pc.name, "✓ OAuth sign-in complete"))
            except Exception as exc:
                self.root.after(0, lambda: self._set_status(pc.name, f"✗ {exc}"))

        threading.Thread(target=work, daemon=True).start()

    def run(self) -> None:
        self.root.mainloop()


def run_login(config_path: str | Path) -> None:
    config = load_config(config_path)
    store = CredentialStore()
    ledger = Ledger(config.resolved_ledger_path)
    LoginWindow(config, store, ledger).run()
