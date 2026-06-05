"""The login / accounts window.

Start empty; pick a service from the **Add a service** dropdown to add it. Each
added service shows a logo, an info ("i") button with how-to-get-the-key steps,
a masked key field with **Validate & Save** (which loads live limits in one
step), and **Remove**. Only added services appear — here, in the dashboard, and
in the tray.

Tracks the *developer API* (your API key), not the consumer web/app
subscription. Runs on the main thread (launched via ``token-counter login``).
"""

from __future__ import annotations

import json
import threading
import webbrowser
from pathlib import Path

from . import catalog
from .auth import CredentialStore
from .config import AppConfig, ProviderConfig, add_provider, load_config, remove_provider
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
    def __init__(self, config: AppConfig, store: CredentialStore, ledger: Ledger,
                 config_path: str):
        import tkinter as tk
        from tkinter import ttk

        self.tk = tk
        self.ttk = ttk
        self.config = config
        self.config_path = config_path
        self.store = store
        self.ledger = ledger
        self._photos: list = []
        self._status_vars: dict[str, "tk.StringVar"] = {}
        self._entries: dict[str, "tk.Entry"] = {}

        from .fonts import app_font_family

        self.root = tk.Tk()
        self.root.title("tokn — Accounts")
        self.root.geometry("720x520")
        self.root.minsize(620, 420)
        self._set_icon(self.root)

        header = ttk.Frame(self.root, padding=(16, 14, 16, 4))
        header.pack(fill="x")
        ttk.Label(header, text="tokn", font=(app_font_family(), 22, "bold")).pack(anchor="w")
        ttk.Label(
            header,
            text=(f"Sign in to your AI services (developer API keys). "
                  f"Stored securely via: {store.backend}."),
            foreground="#555",
        ).pack(anchor="w")

        # Add-a-service row
        addbar = ttk.Frame(self.root, padding=(16, 8))
        addbar.pack(fill="x")
        ttk.Label(addbar, text="Add a service:").pack(side="left")
        self._add_var = tk.StringVar()
        self._combo = ttk.Combobox(addbar, textvariable=self._add_var, state="readonly", width=24)
        self._combo.pack(side="left", padx=8)
        ttk.Button(addbar, text="Add", command=self._on_add).pack(side="left")

        ttk.Separator(self.root, orient="horizontal").pack(fill="x", padx=16, pady=4)

        # Scrollable list of added services
        self.body = ttk.Frame(self.root, padding=(16, 4))
        self.body.pack(fill="both", expand=True)

        self._render()

    # --- helpers -------------------------------------------------------
    def _set_icon(self, win) -> None:
        try:
            from .window_ui import _set_window_icon

            _set_window_icon(win, self._photos)
        except Exception:
            pass

    def _added_names(self) -> list[str]:
        return [pc.name for pc in self.config.providers]

    def _reload(self) -> None:
        self.config = load_config(self.config_path)

    def _refresh_combo(self) -> None:
        added = set(self._added_names())
        avail = [(k, catalog.SERVICES[k].display_name) for k in catalog.service_keys()
                 if k not in added]
        self._combo_map = {name: key for key, name in avail}
        self._combo["values"] = [name for _k, name in avail]
        self._add_var.set(avail[0][1] if avail else "")

    # --- rendering -----------------------------------------------------
    def _render(self) -> None:
        for w in self.body.winfo_children():
            w.destroy()
        self._status_vars.clear()
        self._entries.clear()
        self._refresh_combo()

        providers = self.config.providers
        if not providers:
            self.ttk.Label(
                self.body,
                text="No services yet — pick one above and click Add.",
                foreground="#777",
            ).pack(anchor="w", pady=20)
            return

        for pc in providers:
            self._build_service_row(pc)

    def _build_service_row(self, pc: ProviderConfig) -> None:
        tk, ttk = self.tk, self.ttk
        svc = catalog.get(pc.name)
        title = (svc.display_name if svc else pc.name)

        frame = ttk.LabelFrame(self.body, text=f"  {title}  ", padding=10)
        frame.pack(fill="x", pady=6)

        top = ttk.Frame(frame)
        top.pack(fill="x")

        # Logo
        try:
            from .logos import provider_logo_image
            from .window_ui import _photo

            logo = _photo(provider_logo_image(pc.name, 24, pc.option("scheme")), self._photos)
            tk.Label(top, image=logo).pack(side="left")
        except Exception:
            pass

        ttk.Label(top, text=title, font=("Segoe UI", 11, "bold")).pack(side="left", padx=(8, 4))
        if svc is not None:
            ttk.Button(top, text="ⓘ", width=3,
                       command=lambda s=svc: self._show_info(s)).pack(side="left")

        row = ttk.Frame(frame)
        row.pack(fill="x", pady=(8, 0))
        ttk.Label(row, text="API key:").pack(side="left")
        entry = ttk.Entry(row, show="•", width=46)
        existing = self.store.get(pc.name, "api_key")
        if existing:
            entry.insert(0, existing)
        entry.pack(side="left", padx=6)
        self._entries[pc.name] = entry
        ttk.Button(row, text="Validate & Save",
                   command=lambda p=pc: self._save_key(p)).pack(side="left")
        ttk.Button(row, text="Remove",
                   command=lambda p=pc: self._remove(p)).pack(side="left", padx=4)

        status = tk.StringVar(value=self._initial_status(pc))
        self._status_vars[pc.name] = status
        ttk.Label(frame, textvariable=status, foreground="#557").pack(anchor="w", pady=(6, 0))

    def _show_info(self, svc: "catalog.Service") -> None:
        tk, ttk = self.tk, self.ttk
        top = tk.Toplevel(self.root)
        top.title(f"{svc.display_name} — how to add your key")
        top.geometry("460x260")
        self._set_icon(top)
        ttk.Label(top, text=f"{svc.display_name} API key", font=("Segoe UI", 12, "bold"),
                  padding=(14, 12, 14, 4)).pack(anchor="w")
        ttk.Label(top, text=svc.help, justify="left", padding=(14, 0)).pack(anchor="w")
        btns = ttk.Frame(top, padding=14)
        btns.pack(side="bottom", fill="x")
        ttk.Button(btns, text="Open key page",
                   command=lambda: webbrowser.open(svc.key_url)).pack(side="left")
        ttk.Button(btns, text="Close", command=top.destroy).pack(side="right")

    # --- actions -------------------------------------------------------
    def _on_add(self) -> None:
        name = self._add_var.get().strip()
        key = getattr(self, "_combo_map", {}).get(name)
        if not key:
            return
        add_provider(self.config_path, key)
        self._reload()
        self._render()

    def _initial_status(self, pc: ProviderConfig) -> str:
        if self.store.get(pc.name, "api_key"):
            return "✓ key stored"
        return "not signed in"

    def _set_status(self, name: str, text: str) -> None:
        if name in self._status_vars:
            self._status_vars[name].set(text)

    def _save_key(self, pc: ProviderConfig) -> None:
        secret = self._entries[pc.name].get().strip()
        if not secret:
            self._set_status(pc.name, "✗ enter an API key first")
            return
        self._set_status(pc.name, "validating & loading limits…")
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
        remove_provider(self.config_path, pc.name)
        self._reload()
        self._render()

    def run(self) -> None:
        self.root.mainloop()


def run_login(config_path: str | Path) -> None:
    from .config import ensure_config

    ensure_config(config_path)
    config = load_config(config_path)
    store = CredentialStore()
    ledger = Ledger(config.resolved_ledger_path)
    LoginWindow(config, store, ledger, str(Path(config_path).expanduser())).run()
