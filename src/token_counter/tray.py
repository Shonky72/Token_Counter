"""Windows system-tray front end.

Hover the icon → tooltip with each provider's enforced limit (used / remaining /
reset countdown). Right-click → full per-window breakdown, "Accounts / Login…",
refresh, and quit. Icon color reflects the worst provider's consumption
(green < 75% < amber < 90% < red).

``pystray`` and ``Pillow`` are imported lazily so the rest of the package (and
the test suite) work headless.
"""

from __future__ import annotations

import subprocess
import sys
import threading
from datetime import datetime, timezone

from .engine import Engine
from .icons import status_icon_image
from .models import Gauge, ProviderStatus
from .render import _primary_gauge, human, overall_percent, tray_title


def _make_icon_image(percent: float | None = None, threshold: int = 90):
    # Brand icon with a small status dot (green/amber/red) for the worst provider.
    return status_icon_image(64, percent, threshold)


def _gauge_label(g: Gauge) -> str:
    if g.limit is None:
        text = f"{g.label}: {human(g.used)}"
    else:
        text = f"{g.label}: {human(g.used)}/{human(g.limit)} ({g.percent:.0f}%)"
    reset = g.reset_in_seconds()
    if reset is not None:
        text += f" · {reset}s"
    return text


class TrayApp:
    def __init__(self, engine: Engine, refresh_seconds: int = 30, server=None,
                 config_path: str | None = None, default_view: str = "dashboard",
                 app_config=None):
        self.engine = engine
        self.refresh_seconds = max(5, refresh_seconds)
        self.server = server
        self.config_path = config_path
        self.default_view = default_view
        cfg = app_config
        self.alerts_enabled = bool(getattr(cfg, "alerts_enabled", True))
        self.alert_threshold = int(getattr(cfg, "alert_threshold", 90))
        self.token_basis = str(getattr(cfg, "token_basis", "used"))
        self.display_metric = str(getattr(cfg, "display_metric", "amount"))
        self.theme = str(getattr(cfg, "theme", "dark"))
        providers = getattr(getattr(engine, "config", None), "providers", []) or []
        self._usage_urls = {pc.name: pc.option("usage_url") for pc in providers}
        self._statuses: list[ProviderStatus] = []
        self._last_pct: dict[str, float] = {}  # for threshold-crossing alerts
        self._last_refresh = None  # local datetime of the last successful refresh
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._icon = None

    def _refresh_label(self, item=None) -> str:
        # pystray calls callable menu text as text(item), so accept the arg.
        when = self._last_refresh.strftime("%H:%M:%S") if self._last_refresh else "never"
        return f"Refresh now (last: {when})"

    def _build_menu(self):
        from pystray import Menu, MenuItem

        with self._lock:
            statuses = list(self._statuses)

        items: list = []
        for s in statuses:
            if s.error:
                items.append(MenuItem(f"{s.provider}: {s.error}", None, enabled=False))
                continue
            header = s.provider + (f"  ({s.detail})" if s.detail else "")
            sub = [MenuItem(_gauge_label(g), None, enabled=False) for g in s.gauges] or [
                MenuItem("no data yet", None, enabled=False)
            ]
            if self._usage_urls.get(s.provider):
                sub = [MenuItem("↗ Open usage page", self._open_usage(s.provider)),
                       Menu.SEPARATOR] + sub
            items.append(MenuItem(header, Menu(*sub)))

        items.append(Menu.SEPARATOR)
        from ._buildinfo import build_string

        items.append(MenuItem(f"tokn v{build_string()}", None, enabled=False))
        # Default action (left-click the tray icon) opens the dashboard.
        items.append(MenuItem("Open dashboard", self._on_dashboard, default=True))
        items.append(MenuItem("Compact view", self._on_popup))
        items.append(MenuItem("Accounts / Login…", self._on_login))
        items.append(MenuItem("Display", self._display_menu()))
        items.append(MenuItem(
            "Open on startup", self._on_toggle_startup, checked=lambda i: self._startup_enabled()
        ))
        items.append(MenuItem(self._refresh_label, self._on_refresh))
        items.append(MenuItem("Quit", self._on_quit))
        return Menu(*items)

    def _display_menu(self):
        from pystray import Menu, MenuItem

        def theme_item(name):
            return MenuItem(name.capitalize(), self._set_theme(name),
                            checked=lambda i, n=name: self.theme == n, radio=True)

        def basis_item(name, label):
            return MenuItem(label, self._set_basis(name),
                            checked=lambda i, n=name: self.token_basis == n, radio=True)

        def metric_item(name, label):
            return MenuItem(label, self._set_metric(name),
                            checked=lambda i, n=name: self.display_metric == n, radio=True)

        return Menu(
            MenuItem("Theme", Menu(theme_item("dark"), theme_item("light"),
                                   theme_item("system"))),
            Menu.SEPARATOR,
            basis_item("used", "Show: used"),
            basis_item("remaining", "Show: remaining"),
            Menu.SEPARATOR,
            metric_item("amount", "As: amount"),
            metric_item("percent", "As: percent"),
        )

    def _save(self, key: str, value) -> None:
        if not self.config_path:
            return
        try:
            from .config import save_setting

            save_setting(self.config_path, key, value)
        except Exception:  # pragma: no cover
            pass

    def _set_theme(self, name):
        def handler(icon=None, item=None):
            self.theme = name
            self._save("theme", name)
        return handler

    def _set_basis(self, name):
        def handler(icon=None, item=None):
            self.token_basis = name
            self._save("token_basis", name)
            self._apply()
        return handler

    def _set_metric(self, name):
        def handler(icon=None, item=None):
            self.display_metric = name
            self._save("display_metric", name)
            self._apply()
        return handler

    def _open_usage(self, provider: str):
        def handler(icon=None, item=None):
            import webbrowser

            url = self._usage_urls.get(provider)
            if url:
                webbrowser.open(url)
        return handler

    @staticmethod
    def _startup_enabled() -> bool:
        from . import startup as startup_mod

        return startup_mod.is_enabled()

    def _apply(self) -> None:
        if self._icon is None:
            return
        with self._lock:
            statuses = list(self._statuses)
        self._icon.title = tray_title(statuses, metric=self.display_metric,
                                      basis=self.token_basis)
        self._icon.icon = _make_icon_image(overall_percent(statuses), self.alert_threshold)
        self._icon.menu = self._build_menu()

    def refresh(self) -> None:
        now = datetime.now(timezone.utc)
        statuses = self.engine.snapshot(now)
        self._record_samples(statuses, now)
        self._check_alerts(statuses)
        with self._lock:
            self._statuses = statuses
            self._last_refresh = datetime.now()  # local time for the menu label
        self._apply()

    def _record_samples(self, statuses, now) -> None:
        """Append a usage sample per provider for the sparkline / burn-rate."""
        try:
            ts = now.timestamp()
            for s in statuses:
                if s.error:
                    continue
                g = _primary_gauge(s)
                if g is None:
                    continue
                self.engine.ledger.record_sample(
                    s.provider, used=g.used, limit=g.limit, percent=g.percent, ts=ts,
                )
            # Keep the samples table small: the sparkline only reads the last 24h,
            # so trim anything older than a week, roughly hourly.
            self._sample_count = getattr(self, "_sample_count", 0) + 1
            if self._sample_count % 120 == 1:
                from datetime import timedelta

                self.engine.ledger.prune_samples(now - timedelta(days=7))
        except Exception as exc:  # pragma: no cover - never break the tray
            print(f"[token-counter] sample record failed: {exc}")

    def _check_alerts(self, statuses) -> None:
        """Notify once when a provider's worst gauge crosses the threshold upward."""
        if not self.alerts_enabled:
            return
        for s in statuses:
            pct = None if s.error else s.worst_percent
            if pct is None:
                continue
            prev = self._last_pct.get(s.provider)
            self._last_pct[s.provider] = pct
            if prev is not None and prev < self.alert_threshold <= pct:
                self._notify(
                    f"{s.provider} is at {pct:.0f}% of its limit.", "tokn — usage alert"
                )

    def _notify(self, message: str, title: str = "tokn") -> None:
        try:  # pystray balloon; not all backends support it
            if self._icon is not None:
                self._icon.notify(message, title)
        except Exception:  # pragma: no cover
            pass

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.refresh()
            except Exception as exc:  # pragma: no cover - keep tray alive
                print(f"[token-counter] refresh failed: {exc}")
            self._stop.wait(self.refresh_seconds)

    # --- menu callbacks ------------------------------------------------
    def _spawn(self, command: str) -> None:
        # Launch a Tkinter window in its own process so it owns the main thread
        # (Tk and pystray can't share one). Frozen-exe aware.
        from .relaunch import popen_kwargs, subprocess_args

        try:
            subprocess.Popen(subprocess_args(command, self.config_path), **popen_kwargs())
        except Exception as exc:  # pragma: no cover
            print(f"[token-counter] could not open {command} window: {exc}")

    def _on_dashboard(self, icon=None, item=None) -> None:
        self._spawn("popup" if self.default_view == "compact" else "window")

    def _on_popup(self, icon=None, item=None) -> None:
        self._spawn("popup")

    def _on_login(self, icon=None, item=None) -> None:
        self._spawn("login")

    def _on_toggle_startup(self, icon=None, item=None) -> None:
        from . import startup as startup_mod
        from .config import save_open_on_startup

        new_value = not startup_mod.is_enabled()
        startup_mod.set_enabled(new_value)
        if self.config_path:
            try:
                save_open_on_startup(self.config_path, new_value)
            except Exception:  # pragma: no cover
                pass
        if self._icon is not None:
            self._icon.update_menu()

    def _on_refresh(self, icon=None, item=None) -> None:
        threading.Thread(target=self.refresh, daemon=True).start()

    def _on_quit(self, icon=None, item=None) -> None:
        self._stop.set()
        if self.server is not None:
            self.server.stop()
        if self._icon is not None:
            self._icon.stop()

    def run(self) -> None:
        import pystray

        # A failed first refresh (network, bad key, etc.) must NOT stop the icon
        # from appearing — otherwise the app looks like it's "running but
        # invisible". Show the icon first, then refresh in the background.
        try:
            self.refresh()
        except Exception as exc:  # pragma: no cover - defensive
            print(f"[token-counter] initial refresh failed: {exc}")
        with self._lock:
            statuses = list(self._statuses)
        self._icon = pystray.Icon(
            "tokn",
            icon=_make_icon_image(overall_percent(statuses), self.alert_threshold),
            title=tray_title(statuses, metric=self.display_metric, basis=self.token_basis),
            menu=self._build_menu(),
        )
        threading.Thread(target=self._loop, daemon=True).start()
        self._icon.run()
