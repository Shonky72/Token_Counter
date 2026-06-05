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
from .icons import tray_meter_image
from .models import Gauge, ProviderStatus
from .render import human, overall_percent, tooltip_text


def _make_icon_image(percent: float | None):
    return tray_meter_image(64, percent)


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
                 config_path: str | None = None, default_view: str = "dashboard"):
        self.engine = engine
        self.refresh_seconds = max(5, refresh_seconds)
        self.server = server
        self.config_path = config_path
        self.default_view = default_view
        self._statuses: list[ProviderStatus] = []
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._icon = None

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
            items.append(MenuItem(header, Menu(*sub)))

        items.append(Menu.SEPARATOR)
        # Default action (left-click the tray icon) opens the dashboard.
        items.append(MenuItem("Open dashboard", self._on_dashboard, default=True))
        items.append(MenuItem("Compact view", self._on_popup))
        items.append(MenuItem("Accounts / Login…", self._on_login))
        items.append(MenuItem(
            "Open on startup", self._on_toggle_startup, checked=lambda i: self._startup_enabled()
        ))
        items.append(MenuItem("Refresh now", self._on_refresh))
        items.append(MenuItem("Quit", self._on_quit))
        return Menu(*items)

    @staticmethod
    def _startup_enabled() -> bool:
        from . import startup as startup_mod

        return startup_mod.is_enabled()

    def _apply(self) -> None:
        if self._icon is None:
            return
        with self._lock:
            statuses = list(self._statuses)
        self._icon.title = "Token Counter\n" + tooltip_text(statuses)
        self._icon.icon = _make_icon_image(overall_percent(statuses))
        self._icon.menu = self._build_menu()

    def refresh(self) -> None:
        statuses = self.engine.snapshot(datetime.now(timezone.utc))
        with self._lock:
            self._statuses = statuses
        self._apply()

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
        from .relaunch import subprocess_args

        try:
            subprocess.Popen(subprocess_args(command, self.config_path))
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

        self.refresh()
        with self._lock:
            statuses = list(self._statuses)
        self._icon = pystray.Icon(
            "token_counter",
            icon=_make_icon_image(overall_percent(statuses)),
            title="Token Counter\n" + tooltip_text(statuses),
            menu=self._build_menu(),
        )
        threading.Thread(target=self._loop, daemon=True).start()
        self._icon.run()
