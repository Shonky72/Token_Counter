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

    def open_settings(self) -> bool:
        self._spawn("settings")
        return True

    def import_usage(self) -> str:
        """Pick a CSV via a native file dialog, import it (auto-routing rows to the
        right card by model name), and reload so the cards show immediately."""
        import webview

        from . import config as config_mod, usage_import

        win = getattr(self, "_window", None)
        paths = None
        if win is not None:
            try:
                paths = win.create_file_dialog(
                    webview.OPEN_DIALOG, allow_multiple=False,
                    file_types=("CSV files (*.csv)", "All files (*.*)"),
                )
            except Exception:
                paths = None
        if not paths:
            return ""  # cancelled
        path = paths[0] if isinstance(paths, (list, tuple)) else paths

        def _ensure(prov: str) -> None:
            config_mod.ensure_provider(self.config_path, prov)

        try:
            result, unknown = usage_import.import_auto(self.engine.ledger, path, _ensure)
        except Exception as exc:
            return f"Import failed: {exc}"

        # reload so a newly-added card is picked up by this window on the next refresh
        try:
            self.config = config_mod.load_config(self.config_path)
            self.engine = _engine_for(self.config)
        except Exception:
            pass

        if not result and not unknown:
            return "No rows found in that file."
        names = {"claude_tracked": "Claude", "gemini": "Gemini"}
        parts = [f"{t:,} tokens → {names.get(p, p)}" for p, (_c, t) in result.items()]
        msg = "Imported " + "; ".join(parts) if parts else "Nothing imported"
        if unknown:
            msg += f" ({unknown} row(s) skipped — unrecognised model)"
        return msg

    def close(self) -> bool:
        win = getattr(self, "_window", None)
        if win is not None:
            try:
                win.destroy()
            except Exception:
                pass
        return True

    # ---- settings page ---------------------------------------------------
    def get_settings(self) -> dict:
        from . import startup, theme as theme_mod

        c = self.config
        supported = startup.is_supported()
        on_startup = startup.is_enabled() if supported else c.open_on_startup
        return {
            "theme": c.theme,
            "resolved_theme": theme_mod.resolve_theme(c.theme),
            "basis": c.token_basis,
            "metric": c.display_metric,
            "show_cost": c.show_cost,
            "show_sparkline": c.show_sparkline,
            "alerts_enabled": c.alerts_enabled,
            "alert_threshold": c.alert_threshold,
            "open_on_startup": bool(on_startup),
            "startup_supported": supported,
            "version": self._version(),
        }

    # whitelist of directly-persistable settings -> coercion
    _SETTINGS = {
        "theme": str, "token_basis": str, "display_metric": str,
        "show_cost": bool, "show_sparkline": bool,
        "alerts_enabled": bool, "alert_threshold": int,
    }

    def set_setting(self, key: str, value) -> dict:
        from . import config as config_mod

        coerce = self._SETTINGS.get(key)
        if coerce is not None:
            config_mod.save_setting(self.config_path, key, coerce(value))
            self.config = config_mod.load_config(self.config_path)
        return self.get_settings()

    def set_startup(self, value) -> dict:
        from . import config as config_mod, startup

        want = bool(value)
        if startup.is_supported():
            startup.set_enabled(want)
        config_mod.save_open_on_startup(self.config_path, want)
        self.config = config_mod.load_config(self.config_path)
        return self.get_settings()

    def export(self, fmt: str = "json") -> str:
        from datetime import datetime, timezone

        from . import reporting

        fmt = "csv" if str(fmt).lower() == "csv" else "json"
        providers = [p.name for p in self.config.providers]
        start = datetime(1970, 1, 1, tzinfo=timezone.utc)
        data = reporting.export_usage(self.engine.ledger, providers, start, fmt)
        out = Path("~/.token_counter").expanduser() / f"tokn-usage.{fmt}"
        out.write_text(data, encoding="utf-8")
        return str(out)


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


# page file + (width, height) per screen
_PAGES = {
    "dashboard": ("dashboard.html", (444, 760)),
    "compact": ("compact.html", (320, 380)),
    "settings": ("settings.html", (470, 620)),
}


def _focus_window(window) -> None:
    """Best-effort bring-to-front when a second launch pings the owner."""
    for method in ("restore", "show"):
        try:
            getattr(window, method)()
        except Exception:
            pass
    try:  # nudge to the top, then drop the always-on-top flag again
        window.on_top = True
        window.on_top = False
    except Exception:
        pass


def _run(screen: str, config_path: str | Path) -> None:
    from .singleton import SingleInstance

    cfg_path = str(Path(config_path).expanduser())
    page, (width, height) = _PAGES.get(screen, _PAGES["dashboard"])

    inst = SingleInstance(screen)
    if not inst.acquire():
        return  # already open elsewhere — we've pinged it to come forward

    try:
        import webview  # noqa: F401  (lazy: avoids a GUI dep on headless/CI imports)
    except Exception:
        inst.close()
        return _fallback(screen, cfg_path)

    try:
        api = Api(cfg_path, screen)
        url = (_assets_dir() / page).as_uri()
        window = webview.create_window(
            "tokn", url=url, js_api=api, width=width, height=height,
            background_color="#141218", resizable=True,
        )
        api._window = window
        inst.set_focus_handler(lambda: _focus_window(window))
        interval = max(5, api.config.refresh_seconds)
        threading.Thread(
            target=_refresh_loop, args=(api, window, interval), daemon=True
        ).start()
        webview.start()
    except Exception:
        # WebView2 runtime missing or the window failed to start.
        inst.close()
        return _fallback(screen, cfg_path)
    finally:
        inst.close()


def _fallback(screen: str, config_path: str) -> None:
    # No Tk equivalent for the settings page; the web window is required there.
    if screen == "settings":
        return
    from .window_ui import run_compact, run_dashboard

    if screen == "compact":
        run_compact(config_path)
    else:
        run_dashboard(config_path)


def run_dashboard(config_path: str | Path) -> None:
    _run("dashboard", config_path)


def run_compact(config_path: str | Path) -> None:
    _run("compact", config_path)


def run_settings(config_path: str | Path) -> None:
    _run("settings", config_path)
