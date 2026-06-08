"""pywebview hosts for the dashboard and compact windows.

Renders the bundled Material 3 design (``assets/web``) on the system Edge
WebView2 via pywebview, fed live data from :mod:`webstate`. A background thread
pushes refreshes by evaluating ``window.tokn.update(<json>)`` in the page.

If pywebview or the WebView2 runtime is unavailable, each entry point falls back
to the Tkinter window (:mod:`window_ui`) so the app always opens *something*.
"""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .auth import CredentialStore, load_credentials_into_env
from .config import AppConfig, load_config
from .engine import Engine
from .ledger import Ledger


def _assets_dir() -> Path:
    return Path(__file__).resolve().parent / "assets" / "web"


def _engine_for(config: AppConfig) -> Engine:
    store = CredentialStore()
    load_credentials_into_env(store, config.providers)
    ledger = Ledger(config.resolved_ledger_path)
    return Engine(config, ledger, store)


class Api:
    """Methods exposed to the page via pywebview's ``js_api``.

    Public methods (no leading underscore) are callable from JavaScript as
    ``window.pywebview.api.<name>(...)``.
    """

    def __init__(self, config_path: str, screen: str) -> None:
        self.config_path = str(Path(config_path).expanduser())
        self.screen = screen
        self.config = load_config(self.config_path)
        self.engine = _engine_for(self.config)
        self._statuses: list = []
        self._lock = threading.Lock()

    # ---- internals -------------------------------------------------------
    def _theme(self) -> str:
        try:
            from . import theme as theme_mod
            return theme_mod.resolve_theme(self.config.theme)
        except Exception:
            return "dark"

    def _version(self) -> str:
        try:
            from ._buildinfo import build_string
            return build_string()
        except Exception:
            return ""

    def _extras(self) -> dict[str, dict]:
        """Per-provider burn-rate / 30-day cost / sparkline from the ledger."""
        from . import analytics, pricing

        out: dict[str, dict] = {}
        now = datetime.now(timezone.utc)
        for s in self._statuses:
            prov = s.provider
            ex: dict = {}
            try:
                samples = self.engine.ledger.samples_since(prov, now - timedelta(hours=24))
                rate = analytics.burn_rate_per_hour(samples)
                if rate > 0:
                    ex["rate"] = analytics.human_rate(rate)
                if self.config.show_sparkline:
                    ex["spark"] = analytics.cumulative_series(samples)
                if self.config.show_cost:
                    usages = self.engine.ledger.usage_since(prov, now - timedelta(days=30))
                    ex["cost"] = pricing.format_cost(pricing.cost_for_usage(usages))
            except Exception:
                pass
            out[prov] = ex
        return out

    def _build(self) -> dict:
        from . import webstate

        return webstate.build_state(
            self.config, self._statuses, theme=self._theme(),
            extras=self._extras(), version=self._version(),
        )

    def _spawn(self, command: str) -> None:
        import subprocess

        from .relaunch import popen_kwargs, subprocess_args

        subprocess.Popen(subprocess_args(command, self.config_path), **popen_kwargs())

    # ---- exposed to JS ---------------------------------------------------
    def get_state(self) -> dict:
        with self._lock:
            self._statuses = self.engine.snapshot()
        return self._build()

    def refresh(self) -> dict:
        return self.get_state()

    def refresh_one(self, name: str) -> dict:
        try:
            updated = self.engine.snapshot_one(name)
            with self._lock:
                self._statuses = [
                    updated if s.provider == name else s for s in self._statuses
                ]
        except Exception:
            pass
        return self._build()

    def open_usage(self, name: str) -> bool:
        url = None
        for card in self._build()["cards"]:
            if card["key"] == name:
                url = card.get("usage_url")
                break
        if url:
            import webbrowser

            webbrowser.open(url)
            return True
        return False

    def open_login(self) -> bool:
        self._spawn("login")
        return True


def _refresh_loop(api: Api, window, interval: int) -> None:
    while True:
        time.sleep(interval)
        try:
            state = api.get_state()
            window.evaluate_js(
                "window.tokn && window.tokn.update(" + json.dumps(state) + ")"
            )
        except Exception:
            break


def _run(screen: str, config_path: str | Path) -> None:
    cfg_path = str(Path(config_path).expanduser())
    page = "compact.html" if screen == "compact" else "dashboard.html"
    width, height = (320, 380) if screen == "compact" else (444, 760)

    try:
        import webview  # noqa: F401  (lazy: avoids a GUI dep on headless/CI imports)
    except Exception:
        return _fallback(screen, cfg_path)

    try:
        api = Api(cfg_path, screen)
        url = (_assets_dir() / page).as_uri()
        window = webview.create_window(
            "tokn", url=url, js_api=api, width=width, height=height,
            background_color="#141218", resizable=True,
        )
        interval = max(5, api.config.refresh_seconds)
        threading.Thread(
            target=_refresh_loop, args=(api, window, interval), daemon=True
        ).start()
        webview.start()
    except Exception:
        # WebView2 runtime missing or the window failed to start.
        return _fallback(screen, cfg_path)


def _fallback(screen: str, config_path: str) -> None:
    from .window_ui import run_compact, run_dashboard

    if screen == "compact":
        run_compact(config_path)
    else:
        run_dashboard(config_path)


def run_dashboard(config_path: str | Path) -> None:
    _run("dashboard", config_path)


def run_compact(config_path: str | Path) -> None:
    _run("compact", config_path)
