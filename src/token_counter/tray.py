"""Windows system-tray front end.

Hover the icon → tooltip with used/remaining per provider. Right-click → full
per-model breakdown, refresh, and quit. The icon color reflects the worst
provider's consumption (green < 75% < amber < 90% < red).

``pystray`` and ``Pillow`` are imported lazily so the rest of the package (and
the test suite) work on a headless box without them.
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, timezone

from .engine import Engine
from .models import BudgetStatus
from .render import detail_text, human, overall_percent, tooltip_text


def _color_for(percent: float | None) -> tuple[int, int, int]:
    if percent is None:
        return (90, 120, 200)  # blue: no limit configured
    if percent >= 90:
        return (210, 60, 60)  # red
    if percent >= 75:
        return (220, 160, 40)  # amber
    return (60, 170, 90)  # green


def _make_icon_image(percent: float | None):
    from PIL import Image, ImageDraw  # local import: optional dependency

    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    color = _color_for(percent)
    draw.ellipse((4, 4, size - 4, size - 4), fill=color)

    # Draw a depletion arc: filled wedge showing how much budget is consumed.
    if percent is not None and percent > 0:
        extent = 360 * min(percent, 100) / 100
        draw.pieslice(
            (4, 4, size - 4, size - 4),
            start=-90,
            end=-90 + extent,
            fill=tuple(min(c + 60, 255) for c in color),
        )
    return img


class TrayApp:
    def __init__(self, engine: Engine, refresh_seconds: int = 30, server=None):
        self.engine = engine
        self.refresh_seconds = max(5, refresh_seconds)
        self.server = server
        self._statuses: list[BudgetStatus] = []
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._icon = None

    # --- rendering -----------------------------------------------------
    def _build_menu(self):
        from pystray import Menu, MenuItem

        with self._lock:
            statuses = list(self._statuses)

        items: list = []
        for s in statuses:
            if s.error:
                items.append(MenuItem(f"{s.provider}: error — {s.error}", None, enabled=False))
                continue
            header = (
                f"{s.provider}: {human(s.used)}"
                + (f" / {human(s.limit)} ({s.percent:.0f}%)" if s.limit else " (no limit)")
            )
            sub = [
                MenuItem(
                    f"{m.model}: {human(m.used)}"
                    + (f" / {human(m.limit)} ({m.percent:.0f}%)" if m.limit else ""),
                    None,
                    enabled=False,
                )
                for m in s.models
            ] or [MenuItem("no usage yet", None, enabled=False)]
            items.append(MenuItem(header, Menu(*sub)))

        items.append(Menu.SEPARATOR)
        items.append(MenuItem("Refresh now", self._on_refresh))
        items.append(MenuItem("Quit", self._on_quit))
        return Menu(*items)

    def _apply(self) -> None:
        if self._icon is None:
            return
        with self._lock:
            statuses = list(self._statuses)
        self._icon.title = "Token Counter\n" + tooltip_text(statuses)
        self._icon.icon = _make_icon_image(overall_percent(statuses))
        self._icon.menu = self._build_menu()

    # --- refresh loop --------------------------------------------------
    def refresh(self) -> None:
        statuses = self.engine.snapshot(datetime.now(timezone.utc))
        with self._lock:
            self._statuses = statuses
        self._apply()

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.refresh()
            except Exception as exc:  # pragma: no cover - keep the tray alive
                print(f"[token-counter] refresh failed: {exc}")
            self._stop.wait(self.refresh_seconds)

    # --- menu callbacks ------------------------------------------------
    def _on_refresh(self, icon=None, item=None) -> None:
        threading.Thread(target=self.refresh, daemon=True).start()

    def _on_quit(self, icon=None, item=None) -> None:
        self._stop.set()
        if self.server is not None:
            self.server.stop()
        if self._icon is not None:
            self._icon.stop()

    # --- entry point ---------------------------------------------------
    def run(self) -> None:
        import pystray

        self.refresh()  # populate before first paint
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
