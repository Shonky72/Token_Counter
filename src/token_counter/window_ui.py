"""The dashboard and compact (hover-style) windows, styled after the mockup.

Both are Tkinter, launched as their own processes (``token-counter window`` /
``token-counter popup``) so Tk owns the main thread and never fights pystray.
They read the same ledger/engine the tray does and refresh on a timer; the reset
countdown ticks every second off each gauge's absolute reset time.

Drawing is plain ``tkinter.Canvas`` (ring = arc, bar = rounded rect), so there
are no image assets to ship. Provider accent colors come from the view-model.
"""

from __future__ import annotations

import math
import time
from pathlib import Path

from . import startup as startup_mod
from .auth import CredentialStore, load_credentials_into_env
from .config import AppConfig, load_config, save_open_on_startup
from .engine import Engine
from .flap import FlapDisplay
from .icons import app_icon_image
from .ledger import Ledger
from .logos import provider_logo_image
from . import state as state_mod
from .viewmodel import (
    CardVM,
    CompactVM,
    build_cards,
    build_compact,
)

# Shared dark palette (see theme.py) so the dashboard + login match.
from .theme import BG, CARD, CARD_BORDER, SUBTEXT, TEXT, TRACK, lighten, mix

# Animation timing (the reveal "flap" must run ≥3s and cascade down the list).
REVEAL_DUR = 3.2      # seconds the split-flap reveal runs per card
STAGGER = 0.30        # seconds between successive cards starting (one-by-one)
EASE_DUR = 0.5        # seconds for a quiet value-change gauge ease
FRAME_MS = 16         # ~60fps master animation clock


def _clamp(v, lo=0.0, hi=100.0):
    return lo if v < lo else hi if v > hi else v


def _ease_out(p: float) -> float:
    return 1 - (1 - p) ** 3


def _hunt_pct(progress: float, target: float) -> float:
    """Gauge percent during a reveal: ramps (with an overshoot) while wobbling,
    then converges exactly on ``target`` — it "doesn't know where to land"."""
    if progress >= 1.0:
        return target
    c1, c3 = 1.70158, 2.70158
    ease_back = 1 + c3 * (progress - 1) ** 3 + c1 * (progress - 1) ** 2  # ease-out-back
    ramp = target * ease_back
    wobble = math.sin(progress * 6 * math.pi) * 22 * (1 - progress)
    return _clamp(ramp + wobble)


def _engine_for(config: AppConfig) -> Engine:
    store = CredentialStore()
    load_credentials_into_env(store, config.providers)
    ledger = Ledger(config.resolved_ledger_path)
    return Engine(config, ledger, store)


def _photo(pil_image, refs: list):
    """Convert a PIL image to a Tk PhotoImage and keep a reference alive."""
    from PIL import ImageTk

    img = ImageTk.PhotoImage(pil_image)
    refs.append(img)
    return img


def _logo_photo(name: str, scheme, size: int, refs: list):
    return _photo(provider_logo_image(name, size, scheme), refs)


def _set_window_icon(root, refs: list):
    try:
        root.iconphoto(True, _photo(app_icon_image(64), refs))
    except Exception:  # pragma: no cover - platform/theme dependent
        pass


def _draw_ring(canvas, x, y, d, percent, accent):
    """Draw a donut gauge with the percentage in the middle."""
    pad = 8
    canvas.create_oval(x, y, x + d, y + d, outline=TRACK, width=pad)
    if percent:
        extent = -max(0.5, percent) * 3.6
        # Soft glow underneath, then the crisp accent arc on top.
        canvas.create_arc(
            x - 2, y - 2, x + d + 2, y + d + 2, start=90, extent=extent,
            outline=lighten(accent, 0.28), width=pad + 4, style="arc",
        )
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
        self._cards: dict = {}
        self._card_keys = None
        self._animators: dict = {}      # provider -> active animation state
        self._anim_running = False

        self.root = tk.Tk()
        self.root.title("tokn")
        self.root.configure(bg=BG)
        self.root.minsize(380, 360)
        # Restore last position/size if we have one, else a sensible default.
        self.root.geometry(state_mod.get("dashboard_geometry", "440x560"))
        self._photos: list = []  # keep refs so Tk doesn't garbage-collect images
        self._save_job = None
        _set_window_icon(self.root, self._photos)
        self.root.bind("<Configure>", self._on_configure)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_header()
        self.body = tk.Frame(self.root, bg=BG)
        self.body.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        self._build_footer()

        self.refresh_data()
        self._tick()  # 1s redraw loop for live countdowns

    # --- chrome --------------------------------------------------------
    def _build_header(self):
        tk = self.tk
        from ._buildinfo import build_string
        from .fonts import app_font_family

        bar = tk.Frame(self.root, bg=BG)
        bar.pack(fill="x", padx=12, pady=(12, 6))
        tk.Label(bar, text="tokn", bg=BG, fg=TEXT,
                 font=(app_font_family(), 15, "bold")).pack(side="left")
        tk.Label(bar, text=f"v{build_string()}", bg=BG, fg=SUBTEXT,
                 font=("Segoe UI", 8)).pack(side="left", padx=(8, 0))
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
        self._update_cards()
        self.root.after(max(5, self.config.refresh_seconds) * 1000, self.refresh_data)

    def _tick(self):
        # Cheap: only refresh the "Resets in…" countdowns once a second so the
        # number animations aren't interrupted by a full rebuild.
        self._update_resets()
        self.root.after(1000, self._tick)

    def _vms(self) -> list[CardVM]:
        return build_cards(self.statuses, self.config.providers)

    def _build_cards(self):
        for w in self.body.winfo_children():
            w.destroy()
        self._cards = {}
        vms = self._vms()
        self._card_keys = [vm.provider for vm in vms]
        self._animators = {}
        if not vms:
            self.tk.Label(
                self.body,
                text="No services yet — click “Sign in / Accounts” below to add one.",
                bg=BG, fg=SUBTEXT, wraplength=380, justify="left",
            ).pack(pady=20)
            return
        for vm in vms:
            self._create_card(vm)
        self._start_cascade()  # flap each card's number in, one-by-one down the list

    def _update_cards(self):
        vms = self._vms()
        if [vm.provider for vm in vms] != getattr(self, "_card_keys", None):
            self._build_cards()
            return
        # Periodic refresh: update quietly. The flap reveal only plays on open;
        # here we just set the new amount and gently ease the gauge if it changed.
        for vm in vms:
            c = self._cards.get(vm.provider)
            if c is None:
                continue
            c["accent"] = vm.accent
            c["sub_var"].set(("⚠ " + vm.error) if vm.error else "\n".join(vm.sub_lines))
            c["reset_var"].set(vm.reset_text or "")
            if vm.provider in self._animators:
                # A reveal/ease is still running — let it finish with fresh targets.
                c["primary_text"], c["ring_pct"] = vm.primary_text, vm.percent
                continue
            if vm.primary_text != c.get("primary_text") or vm.percent != c.get("ring_pct"):
                c["flap"].set_static(vm.primary_text)
                self._register_ease(c, c.get("ring_pct"), vm.percent, vm.accent)
                c["primary_text"], c["ring_pct"] = vm.primary_text, vm.percent

    def _update_resets(self):
        if not self._cards:
            return
        for vm in self._vms():
            c = self._cards.get(vm.provider)
            if c is not None:
                c["reset_var"].set(vm.reset_text or "")

    def _mono_font(self, size=11, weight="bold"):
        from .fonts import app_font_family

        return (app_font_family(), size, weight)

    # --- one card ------------------------------------------------------
    def _create_card(self, vm: CardVM):
        tk = self.tk
        card = tk.Frame(self.body, bg=CARD, highlightbackground=CARD_BORDER,
                        highlightthickness=2)
        card.pack(fill="x", pady=6)
        # Accent left strip for a touch of colour.
        strip = tk.Frame(card, bg=vm.accent, width=3)
        strip.pack(side="left", fill="y")
        inner = tk.Frame(card, bg=CARD)
        inner.pack(side="left", fill="x", expand=True, padx=12, pady=10)

        head = tk.Frame(inner, bg=CARD)
        head.pack(fill="x")
        logo = _logo_photo(vm.service or vm.provider or vm.title, vm.scheme, 22,
                           self._photos)
        tk.Label(head, image=logo, bg=CARD).pack(side="left")
        tk.Label(head, text=vm.title.upper(), bg=CARD, fg=TEXT,
                 font=("Segoe UI", 10, "bold")).pack(side="left", padx=(8, 0))
        # Gentle "live" pulse dot.
        pulse = tk.Canvas(head, width=12, height=12, bg=CARD, highlightthickness=0)
        pulse.pack(side="right")

        reset_var = tk.StringVar(value=vm.reset_text or "")
        sub_var = tk.StringVar(value="\n".join(vm.sub_lines))
        c = {"style": vm.style, "reset_var": reset_var, "sub_var": sub_var,
             "limit": vm.limit, "unit": vm.unit, "accent": vm.accent,
             "pulse": pulse, "card": card, "strip": strip, "provider": vm.provider,
             "primary_text": vm.primary_text, "ring_pct": vm.percent}

        row = tk.Frame(inner, bg=CARD)
        row.pack(fill="x", pady=(8, 0))

        if vm.style == "bar":
            flap = FlapDisplay(row, tk, bg=CARD, font=self._mono_font(11))
            flap.widget().pack(anchor="w")
            canvas = tk.Canvas(row, height=8, bg=CARD, highlightthickness=0)
            canvas.pack(fill="x", pady=(6, 4))
            c["canvas"] = canvas
            subrow = tk.Frame(row, bg=CARD)
            subrow.pack(fill="x")
            tk.Label(subrow, textvariable=sub_var, bg=CARD, fg=SUBTEXT,
                     font=("Segoe UI", 8), justify="left").pack(side="left")
            tk.Label(subrow, textvariable=reset_var, bg=CARD, fg=SUBTEXT,
                     font=("Segoe UI", 9)).pack(side="right")
        else:
            canvas = tk.Canvas(row, width=72, height=72, bg=CARD, highlightthickness=0)
            canvas.pack(side="left")
            c["canvas"] = canvas
            info = tk.Frame(row, bg=CARD)
            info.pack(side="left", fill="x", padx=12)
            flap = FlapDisplay(info, tk, bg=CARD, font=self._mono_font(11))
            flap.widget().pack(anchor="w")
            tk.Label(info, textvariable=sub_var, bg=CARD, fg=SUBTEXT,
                     font=("Segoe UI", 8), justify="left").pack(anchor="w")
            tk.Label(info, textvariable=reset_var, bg=CARD, fg=SUBTEXT,
                     font=("Segoe UI", 9)).pack(anchor="w", pady=(4, 0))

        c["flap"] = flap
        # Reserve width with blank tiles so the cascade doesn't shift layout.
        flap.set_static(" " * max(1, len(vm.primary_text)))
        self._cards[vm.provider] = c
        self._attach_hover(c)
        self._draw_gauge(c, 0, vm.accent)
        self._ensure_pulse()

    # --- reveal cascade + master animation clock -----------------------
    def _start_cascade(self):
        now = time.monotonic()
        for i, prov in enumerate(self._card_keys or []):
            c = self._cards.get(prov)
            if c is None:
                continue
            self._animators[prov] = {
                "kind": "reveal", "c": c, "text": c["primary_text"],
                "tpct": c["ring_pct"] or 0, "ring": c["ring_pct"],
                "accent": c["accent"], "start": now + i * STAGGER, "dur": REVEAL_DUR,
            }
        self._ensure_anim_loop()

    def _register_ease(self, c, from_pct, to_pct, accent):
        if from_pct is None or to_pct is None:
            self._draw_gauge(c, to_pct, accent)
            return
        self._animators[c["provider"]] = {
            "kind": "ease", "c": c, "from": from_pct, "to": to_pct,
            "accent": accent, "start": time.monotonic(), "dur": EASE_DUR,
        }
        self._ensure_anim_loop()

    def _ensure_anim_loop(self):
        if self._anim_running or not self._animators:
            return
        self._anim_running = True
        self._anim_loop()

    def _anim_loop(self):
        now = time.monotonic()
        done = []
        for key, a in list(self._animators.items()):
            c = a["c"]
            p = (now - a["start"]) / a["dur"]
            if p < 0:
                p = 0.0
            prog = min(1.0, p)
            try:
                if a["kind"] == "reveal":
                    c["flap"].render_progress(a["text"], prog, a["accent"])
                    if prog >= 1.0:
                        self._draw_gauge(c, a["ring"], a["accent"])
                        done.append(key)
                    else:
                        self._draw_gauge(c, _hunt_pct(prog, a["tpct"]), a["accent"])
                else:  # ease
                    val = a["from"] + (a["to"] - a["from"]) * _ease_out(prog)
                    self._draw_gauge(c, a["to"] if prog >= 1.0 else val, a["accent"])
                    if prog >= 1.0:
                        done.append(key)
            except Exception:
                done.append(key)
        for k in done:
            self._animators.pop(k, None)
        if self._animators:
            try:
                self.root.after(FRAME_MS, self._anim_loop)
            except Exception:
                self._anim_running = False
        else:
            self._anim_running = False

    # --- hover highlight ----------------------------------------------
    def _attach_hover(self, c):
        card, strip, accent = c["card"], c["strip"], c["accent"]
        state = {"n": 0}

        def enter(_):
            state["n"] += 1
            try:
                card.configure(highlightbackground=accent)
                strip.configure(bg=lighten(accent, 0.2))
            except Exception:
                pass

        def leave(_):
            state["n"] -= 1
            if state["n"] <= 0:
                state["n"] = 0
                try:
                    card.configure(highlightbackground=CARD_BORDER)
                    strip.configure(bg=accent)
                except Exception:
                    pass

        def walk(w):
            w.bind("<Enter>", enter, add="+")
            w.bind("<Leave>", leave, add="+")
            for child in w.winfo_children():
                walk(child)

        walk(card)

    # --- live pulse ----------------------------------------------------
    def _ensure_pulse(self):
        if getattr(self, "_pulse_running", False):
            return
        self._pulse_running = True
        self._pulse_phase = 0.0
        self._pulse_tick()

    def _pulse_tick(self):
        import math

        self._pulse_phase = (self._pulse_phase + 0.18) % (2 * math.pi)
        level = 0.5 + 0.5 * math.sin(self._pulse_phase)  # 0..1
        for c in self._cards.values():
            canvas = c.get("pulse")
            if canvas is None:
                continue
            try:
                canvas.delete("all")
                r = 2.5 + 1.6 * level
                col = mix(CARD, c.get("accent", "#5a78c8"), 0.35 + 0.65 * level)
                canvas.create_oval(6 - r, 6 - r, 6 + r, 6 + r, fill=col, outline="")
            except Exception:
                pass
        try:
            self.root.after(90, self._pulse_tick)
        except Exception:
            self._pulse_running = False

    def _draw_gauge(self, c, percent, accent):
        canvas = c.get("canvas")
        if canvas is None:
            return
        p = None if percent is None else int(round(percent))
        canvas.delete("all")
        if c["style"] == "bar":
            canvas.update_idletasks()
            w = max(canvas.winfo_width(), 360)
            _draw_bar(canvas, 0, 0, w, 8, p or 0, accent)
        else:
            _draw_ring(canvas, 4, 4, 64, p, accent)

    # --- window position memory ----------------------------------------
    def _on_configure(self, event):
        if event.widget is not self.root:
            return
        if self._save_job is not None:
            try:
                self.root.after_cancel(self._save_job)
            except Exception:
                pass
        self._save_job = self.root.after(500, self._save_geometry)

    def _save_geometry(self):
        try:
            state_mod.set("dashboard_geometry", self.root.geometry())
        except Exception:
            pass

    def _on_close(self):
        self._save_geometry()
        self.root.destroy()

    # --- actions -------------------------------------------------------
    def _open_login(self):
        import subprocess

        from .relaunch import subprocess_args

        try:
            subprocess.Popen(subprocess_args("login", self.config_path))
        except Exception as exc:  # pragma: no cover
            print(f"[token-counter] could not open login: {exc}")

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
            top, text="Open tokn on Windows startup",
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
        return "Registered to launch at login." if startup_mod.is_enabled() else "Not registered."

    def _toggle_startup(self):
        value = self.startup_var.get()
        detail = ""
        if startup_mod.is_supported():
            ok, detail = startup_mod.set_enabled_detailed(value)
            if not ok:
                self.startup_var.set(not value)  # revert the checkbox on failure
        # Persist the preference to config regardless of platform.
        try:
            save_open_on_startup(self.dash.config_path, value)
        except Exception:
            pass
        # Show the concrete outcome (exact command registered, or the real error).
        self.status.config(text=detail or self._startup_status())


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
        self._photos: list = []

        self._rows: dict = {}
        self._row_keys: list = []
        self._animators: dict = {}
        self._anim_running = False

        self.frame = tk.Frame(self.root, bg=CARD, padx=10, pady=8)
        self.frame.pack(padx=1, pady=1)
        self._build()
        self._position()
        self._start_cascade()
        self.root.bind("<FocusOut>", lambda e: self.root.destroy())
        self.root.bind("<Escape>", lambda e: self.root.destroy())
        self.root.after(max(5, config.refresh_seconds) * 1000, self._refresh)

    def _mono_font(self, size=10, weight="bold"):
        from .fonts import app_font_family

        return (app_font_family(), size, weight)

    def _build(self):
        for w in self.frame.winfo_children():
            w.destroy()
        self._rows = {}
        tk = self.tk
        rows: list[CompactVM] = build_compact(self.engine.snapshot(), self.config.providers)
        self._row_keys = [vm.provider for vm in rows]
        if not rows:
            tk.Label(self.frame, text="No providers", bg=CARD, fg=SUBTEXT).pack()
            return
        for vm in rows:
            r = tk.Frame(self.frame, bg=CARD)
            r.pack(fill="x", pady=3)
            logo = _logo_photo(vm.service or vm.provider or vm.title, vm.scheme, 18,
                               self._photos)
            tk.Label(r, image=logo, bg=CARD).pack(side="left")
            tk.Label(r, text=vm.title, bg=CARD, fg=TEXT,
                     font=("Segoe UI", 10, "bold")).pack(side="left", padx=6)
            flap = FlapDisplay(r, tk, bg=CARD, font=self._mono_font(9),
                               tile_w=9, tile_h=16, fg=SUBTEXT)
            flap.widget().pack(side="right")
            flap.set_static(" " * max(1, len(vm.primary_text)))
            bar = tk.Canvas(self.frame, height=5, width=260, bg=CARD, highlightthickness=0)
            bar.pack(fill="x")
            self._rows[vm.provider] = {"flap": flap, "bar": bar, "text": vm.primary_text,
                                       "pct": vm.percent, "accent": vm.accent}
            _draw_bar(bar, 0, 0, 260, 5, 0, vm.accent)

    def _refresh(self):
        rows: list[CompactVM] = build_compact(self.engine.snapshot(), self.config.providers)
        if [vm.provider for vm in rows] != self._row_keys:
            self._build()
            self._start_cascade()
        else:
            for vm in rows:  # quiet update
                row = self._rows.get(vm.provider)
                if row is None or vm.provider in self._animators:
                    continue
                if vm.primary_text != row["text"]:
                    row["flap"].set_static(vm.primary_text)
                    row["text"] = vm.primary_text
                row["pct"] = vm.percent
                _draw_bar(row["bar"], 0, 0, 260, 5, vm.percent or 0, vm.accent)
        self.root.after(max(5, self.config.refresh_seconds) * 1000, self._refresh)

    # --- cascade reveal (shared with the dashboard's approach) ----------
    def _start_cascade(self):
        now = time.monotonic()
        for i, prov in enumerate(self._row_keys):
            row = self._rows.get(prov)
            if row is None:
                continue
            self._animators[prov] = {"row": row, "start": now + i * STAGGER,
                                     "dur": REVEAL_DUR}
        self._ensure_anim_loop()

    def _ensure_anim_loop(self):
        if self._anim_running or not self._animators:
            return
        self._anim_running = True
        self._anim_loop()

    def _anim_loop(self):
        now = time.monotonic()
        done = []
        for key, a in list(self._animators.items()):
            row = a["row"]
            p = (now - a["start"]) / a["dur"]
            prog = 0.0 if p < 0 else min(1.0, p)
            try:
                row["flap"].render_progress(row["text"], prog, row["accent"])
                pct = (row["pct"] or 0) if prog >= 1.0 else _hunt_pct(prog, row["pct"] or 0)
                _draw_bar(row["bar"], 0, 0, 260, 5, pct, row["accent"])
                if prog >= 1.0:
                    done.append(key)
            except Exception:
                done.append(key)
        for k in done:
            self._animators.pop(k, None)
        if self._animators:
            try:
                self.root.after(FRAME_MS, self._anim_loop)
            except Exception:
                self._anim_running = False
        else:
            self._anim_running = False

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
