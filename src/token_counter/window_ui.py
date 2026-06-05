"""The dashboard and compact (hover-style) windows, styled after the mockup.

Both are Tkinter, launched as their own processes (``token-counter window`` /
``token-counter popup``) so Tk owns the main thread and never fights pystray.
They read the same ledger/engine the tray does and refresh on a timer; the reset
countdown ticks every second off each gauge's absolute reset time.

Drawing is plain ``tkinter.Canvas`` (ring = arc, bar = rounded rect), so there
are no image assets to ship. Provider accent colors come from the view-model.
"""

from __future__ import annotations

from pathlib import Path

from . import startup as startup_mod
from .auth import CredentialStore, load_credentials_into_env
from .config import AppConfig, load_config, save_open_on_startup
from .engine import Engine
from .ledger import Ledger
from .viewmodel import CardVM, CompactVM, build_cards, build_compact

# Dark theme palette (matches the mockup).
BG = "#1b1b1d"
CARD = "#262629"
CARD_BORDER = "#333338"
TEXT = "#ececed"
SUBTEXT = "#9a9aa2"
TRACK = "#3a3a40"


def _engine_for(config: AppConfig) -> Engine:
    store = CredentialStore()
    load_credentials_into_env(store, config.providers)
    ledger = Ledger(config.resolved_ledger_path)
    return Engine(config, ledger, store)


def _draw_ring(canvas, x, y, d, percent, accent):
    """Draw a donut gauge with the percentage in the middle."""
    pad = 8
    canvas.create_oval(x, y, x + d, y + d, outline=TRACK, width=pad)
    if percent:
        extent = -max(0.5, percent) * 3.6
        canvas.create_arc(
            x, y, x + d, y + d, start=90, extent=extent,
            outline=accent, width=pad, style="arc",
        )
    canvas.create_text(
        x + d / 2, y + d / 2,
        text=f"{percent}%" if percent is not None else "—",
        fill=TEXT, font=("Segoe UI", 13, "bold"),
    )


def _draw_bar(canvas, x, y, w, h, percent, accent):
    r = h / 2
    canvas.create_oval(x, y, x + h, y + h, fill=TRACK, outline=TRACK)
    canvas.create_oval(x + w - h, y, x + w, y + h, fill=TRACK, outline=TRACK)
    canvas.create_rectangle(x + r, y, x + w - r, y + h, fill=TRACK, outline=TRACK)
    if percent:
        fw = max(h, (w) * min(percent, 100) / 100)
        canvas.create_oval(x, y, x + h, y + h, fill=accent, outline=accent)
        canvas.create_oval(x + fw - h, y, x + fw, y + h, fill=accent, outline=accent)
        canvas.create_rectangle(x + r, y, x + fw - r, y + h, fill=accent, outline=accent)


class Dashboard:
    def __init__(self, config: AppConfig, config_path: str):
        import tkinter as tk

        self.tk = tk
        self.config = config
        self.config_path = config_path
        self.engine = _engine_for(config)
        self.statuses = []

        self.root = tk.Tk()
        self.root.title("Token Counter")
        self.root.configure(bg=BG)
        self.root.geometry("440x560")
        self.root.minsize(380, 360)

        self._build_header()
        self.body = tk.Frame(self.root, bg=BG)
        self.body.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        self._build_footer()

        self.refresh_data()
        self._tick()  # 1s redraw loop for live countdowns

    # --- chrome --------------------------------------------------------
    def _build_header(self):
        tk = self.tk
        bar = tk.Frame(self.root, bg=BG)
        bar.pack(fill="x", padx=12, pady=(12, 6))
        tk.Label(bar, text="TOKEN TRACKER", bg=BG, fg=TEXT,
                 font=("Segoe UI", 11, "bold")).pack(side="left")
        tk.Button(bar, text="⚙ Settings", command=self._open_settings,
                  bg=BG, fg=SUBTEXT, relief="flat", activebackground=CARD,
                  activeforeground=TEXT, cursor="hand2").pack(side="right")

    def _build_footer(self):
        tk = self.tk
        foot = tk.Frame(self.root, bg=BG)
        foot.pack(fill="x", side="bottom", padx=12, pady=8)
        tk.Label(foot, text="🌐 Global controls", bg=BG, fg=SUBTEXT,
                 font=("Segoe UI", 9)).pack(side="left")
        tk.Button(foot, text="Sign in / Accounts", command=self._open_login,
                  bg=CARD, fg=TEXT, relief="flat", activebackground=CARD_BORDER,
                  activeforeground=TEXT, cursor="hand2").pack(side="right")

    # --- data + render -------------------------------------------------
    def refresh_data(self):
        try:
            self.statuses = self.engine.snapshot()
        except Exception as exc:  # pragma: no cover - keep window alive
            print(f"[token-counter] dashboard refresh failed: {exc}")
        self.root.after(max(5, self.config.refresh_seconds) * 1000, self.refresh_data)

    def _tick(self):
        self._render()
        self.root.after(1000, self._tick)

    def _render(self):
        for w in self.body.winfo_children():
            w.destroy()
        cards = build_cards(self.statuses, self.config.providers)
        if not cards:
            self.tk.Label(self.body, text="No providers configured.",
                          bg=BG, fg=SUBTEXT).pack(pady=20)
        for vm in cards:
            self._render_card(vm)

    def _render_card(self, vm: CardVM):
        tk = self.tk
        card = tk.Frame(self.body, bg=CARD, highlightbackground=CARD_BORDER,
                        highlightthickness=1)
        card.pack(fill="x", pady=6)
        inner = tk.Frame(card, bg=CARD)
        inner.pack(fill="x", padx=12, pady=10)

        head = tk.Frame(inner, bg=CARD)
        head.pack(fill="x")
        tk.Canvas(head, width=12, height=12, bg=CARD, highlightthickness=0).pack(side="left")
        dot = head.winfo_children()[-1]
        dot.create_oval(2, 2, 11, 11, fill=vm.accent, outline=vm.accent)
        tk.Label(head, text=vm.title.upper(), bg=CARD, fg=TEXT,
                 font=("Segoe UI", 10, "bold")).pack(side="left", padx=(6, 0))

        row = tk.Frame(inner, bg=CARD)
        row.pack(fill="x", pady=(8, 0))

        if vm.error:
            tk.Label(row, text=f"⚠ {vm.error}", bg=CARD, fg=SUBTEXT,
                     wraplength=360, justify="left").pack(anchor="w")
            return

        if vm.style == "bar":
            text_col = tk.Frame(row, bg=CARD)
            text_col.pack(fill="x")
            big = tk.Frame(text_col, bg=CARD)
            big.pack(fill="x")
            tk.Label(big, text=f"{vm.percent}%" if vm.percent is not None else "—",
                     bg=CARD, fg=TEXT, font=("Segoe UI", 13, "bold")).pack(side="left")
            bar = tk.Canvas(text_col, height=8, bg=CARD, highlightthickness=0)
            bar.pack(fill="x", pady=(8, 4))
            bar.update_idletasks()
            _draw_bar(bar, 0, 0, max(bar.winfo_width(), 360), 8, vm.percent or 0, vm.accent)
            sub = tk.Frame(text_col, bg=CARD)
            sub.pack(fill="x")
            tk.Label(sub, text=vm.primary_text, bg=CARD, fg=SUBTEXT,
                     font=("Segoe UI", 9)).pack(side="left")
            if vm.reset_text:
                tk.Label(sub, text=vm.reset_text, bg=CARD, fg=SUBTEXT,
                         font=("Segoe UI", 9)).pack(side="right")
        else:
            ring = tk.Canvas(row, width=72, height=72, bg=CARD, highlightthickness=0)
            ring.pack(side="left")
            _draw_ring(ring, 4, 4, 64, vm.percent, vm.accent)
            info = tk.Frame(row, bg=CARD)
            info.pack(side="left", fill="x", padx=12)
            tk.Label(info, text=vm.primary_text, bg=CARD, fg=TEXT,
                     font=("Consolas", 13, "bold")).pack(anchor="w")
            for line in vm.sub_lines:
                tk.Label(info, text=line, bg=CARD, fg=SUBTEXT,
                         font=("Segoe UI", 8)).pack(anchor="w")
            if vm.reset_text:
                tk.Label(info, text=vm.reset_text, bg=CARD, fg=SUBTEXT,
                         font=("Segoe UI", 9)).pack(anchor="w", pady=(4, 0))

    # --- actions -------------------------------------------------------
    def _open_login(self):
        import subprocess
        import sys

        subprocess.Popen([sys.executable, "-m", "token_counter", "login", "-c", self.config_path])

    def _open_settings(self):
        SettingsDialog(self)

    def run(self):
        self.root.mainloop()


class SettingsDialog:
    """Small modal: open-on-startup toggle + refresh interval display."""

    def __init__(self, dashboard: "Dashboard"):
        tk = dashboard.tk
        self.dash = dashboard
        top = tk.Toplevel(dashboard.root, bg=BG)
        top.title("Settings")
        top.geometry("360x200")
        top.transient(dashboard.root)

        tk.Label(top, text="Settings", bg=BG, fg=TEXT,
                 font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=16, pady=(14, 8))

        self.startup_var = tk.BooleanVar(value=startup_mod.is_enabled())
        chk = tk.Checkbutton(
            top, text="Open Token Counter on Windows startup",
            variable=self.startup_var, command=self._toggle_startup,
            bg=BG, fg=TEXT, selectcolor=CARD, activebackground=BG,
            activeforeground=TEXT, anchor="w",
        )
        chk.pack(fill="x", padx=16)

        self.status = tk.Label(top, text=self._startup_status(), bg=BG, fg=SUBTEXT,
                               font=("Segoe UI", 8), anchor="w", wraplength=320, justify="left")
        self.status.pack(fill="x", padx=16, pady=(2, 10))

        tk.Label(top, text=f"Refreshes every {dashboard.config.refresh_seconds}s",
                 bg=BG, fg=SUBTEXT, font=("Segoe UI", 9)).pack(anchor="w", padx=16)

        tk.Button(top, text="Close", command=top.destroy, bg=CARD, fg=TEXT,
                  relief="flat", activebackground=CARD_BORDER).pack(pady=14)

    def _startup_status(self) -> str:
        if not startup_mod.is_supported():
            return "Startup registration is only available on Windows."
        return "Registered in HKCU Run." if startup_mod.is_enabled() else "Not registered."

    def _toggle_startup(self):
        value = self.startup_var.get()
        if startup_mod.is_supported():
            ok = startup_mod.set_enabled(value)
            if not ok:
                self.startup_var.set(not value)
        # Persist the preference to config regardless of platform.
        try:
            save_open_on_startup(self.dash.config_path, value)
        except Exception:
            pass
        self.status.config(text=self._startup_status())


class CompactPopup:
    """Borderless summary near the bottom-right, like the hover tooltip."""

    def __init__(self, config: AppConfig, config_path: str):
        import tkinter as tk

        self.tk = tk
        self.config = config
        self.engine = _engine_for(config)

        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.configure(bg=CARD_BORDER)
        self.root.attributes("-topmost", True)

        self.frame = tk.Frame(self.root, bg=CARD, padx=10, pady=8)
        self.frame.pack(padx=1, pady=1)
        self._render()
        self._position()
        self.root.bind("<FocusOut>", lambda e: self.root.destroy())
        self.root.bind("<Escape>", lambda e: self.root.destroy())
        self.root.after(max(5, config.refresh_seconds) * 1000, self._refresh)

    def _refresh(self):
        self._render()
        self.root.after(max(5, self.config.refresh_seconds) * 1000, self._refresh)

    def _render(self):
        for w in self.frame.winfo_children():
            w.destroy()
        tk = self.tk
        rows: list[CompactVM] = build_compact(self.engine.snapshot(), self.config.providers)
        if not rows:
            tk.Label(self.frame, text="No providers", bg=CARD, fg=SUBTEXT).pack()
        for vm in rows:
            r = tk.Frame(self.frame, bg=CARD)
            r.pack(fill="x", pady=3)
            dot = tk.Canvas(r, width=12, height=12, bg=CARD, highlightthickness=0)
            dot.pack(side="left")
            dot.create_oval(2, 2, 11, 11, fill=vm.accent, outline=vm.accent)
            tk.Label(r, text=vm.title, bg=CARD, fg=TEXT,
                     font=("Segoe UI", 10, "bold")).pack(side="left", padx=6)
            tk.Label(r, text=vm.primary_text, bg=CARD, fg=SUBTEXT,
                     font=("Segoe UI", 9)).pack(side="right")
            bar = tk.Canvas(self.frame, height=5, width=260, bg=CARD, highlightthickness=0)
            bar.pack(fill="x")
            _draw_bar(bar, 0, 0, 260, 5, vm.percent or 0, vm.accent)

    def _position(self):
        self.root.update_idletasks()
        w, h = self.root.winfo_width(), self.root.winfo_height()
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(f"+{sw - w - 20}+{sh - h - 60}")
        self.root.focus_force()

    def run(self):
        self.root.mainloop()


def run_dashboard(config_path: str | Path) -> None:
    config = load_config(config_path)
    Dashboard(config, str(Path(config_path).expanduser())).run()


def run_compact(config_path: str | Path) -> None:
    config = load_config(config_path)
    CompactPopup(config, str(Path(config_path).expanduser())).run()
