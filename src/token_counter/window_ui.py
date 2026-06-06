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
import threading
import time
import webbrowser
from datetime import datetime, timedelta, timezone
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
    build_card,
    build_cards,
    build_compact,
)

# Shared palette (see theme.py) — set by app.main before this module imports.
from .theme import (
    BG,
    CARD,
    CARD_BORDER,
    CARD_HOVER,
    FLAP_FG,
    SUBTEXT,
    TEXT,
    TILE_BG,
    TRACK,
    lighten,
    mix,
)

# Animation timing (the reveal "flap" must run ≥3s and cascade down the list).
REVEAL_DUR = 2.0      # seconds the split-flap reveal runs per card
STAGGER = 0.22        # seconds between successive cards starting (one-by-one)
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

        self.root.bind("<FocusIn>", self._on_focus, add="+")
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
        interval = max(5, self.config.refresh_seconds)
        ok = True
        try:
            self.statuses = self.engine.snapshot()
        except Exception as exc:  # pragma: no cover - keep window alive
            ok = False
            print(f"[token-counter] dashboard refresh failed: {exc}")
        self._update_cards()
        # Back off briefly after a failure (likely offline), then resume; and if
        # the wall clock jumped (laptop woke from sleep), refresh again promptly.
        delay = interval if ok else min(interval, 8)
        self._last_refresh_mono = time.monotonic()
        self.root.after(int(delay * 1000), self.refresh_data)

    def _on_focus(self, _event=None):
        # Refresh when the user returns to the window (covers wake-from-sleep and
        # network coming back), throttled so it isn't spammy.
        last = getattr(self, "_last_refresh_mono", 0.0)
        if time.monotonic() - last < 3:
            return
        try:
            self.statuses = self.engine.snapshot()
            self._last_refresh_mono = time.monotonic()
            self._update_cards()
        except Exception:
            pass

    def _tick(self):
        # Cheap: only refresh the "Resets in…" countdowns once a second so the
        # number animations aren't interrupted by a full rebuild.
        self._update_resets()
        self.root.after(1000, self._tick)

    def _vms(self) -> list[CardVM]:
        return build_cards(self.statuses, self.config.providers,
                           metric=self.config.display_metric, basis=self.config.token_basis)

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
            c["hover_text"] = vm.hover_text
            c["remaining"] = max(vm.limit - vm.used, 0) if vm.limit is not None else None
            c["sub_var"].set(("⚠ " + vm.error) if vm.error else "\n".join(vm.sub_lines))
            c["reset_var"].set(vm.reset_text or "")
            self._update_extras(c)
            if vm.provider in self._animators:
                # A reveal/ease is still running — let it finish with fresh targets.
                c["primary_text"], c["ring_pct"] = vm.primary_text, vm.percent
                continue
            if vm.primary_text != c.get("primary_text") or vm.percent != c.get("ring_pct"):
                # Don't yank the number out from under the cursor mid-hover.
                shown = vm.hover_text if c.get("_hovering") and vm.hover_text else vm.primary_text
                c["flap"].set_static(shown)
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
                        highlightthickness=2, cursor="hand2")
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
        # Gentle "live" pulse dot + per-card refresh.
        pulse = tk.Canvas(head, width=12, height=12, bg=CARD, highlightthickness=0)
        pulse.pack(side="right")
        refresh_btn = tk.Button(head, text="⟳", bg=CARD, fg=SUBTEXT, relief="flat",
                                activebackground=CARD_HOVER, activeforeground=TEXT,
                                cursor="hand2", bd=0,
                                command=lambda p=vm.provider: self._refresh_card(p))
        refresh_btn.pack(side="right", padx=(0, 6))

        reset_var = tk.StringVar(value=vm.reset_text or "")
        sub_var = tk.StringVar(value="\n".join(vm.sub_lines))
        extra_var = tk.StringVar(value="")
        c = {"style": vm.style, "reset_var": reset_var, "sub_var": sub_var,
             "extra_var": extra_var, "limit": vm.limit, "unit": vm.unit,
             "accent": vm.accent, "pulse": pulse, "card": card, "strip": strip,
             "provider": vm.provider, "primary_text": vm.primary_text,
             "hover_text": vm.hover_text, "ring_pct": vm.percent,
             "usage_url": vm.usage_url,
             "remaining": max(vm.limit - vm.used, 0) if vm.limit is not None else None}

        row = tk.Frame(inner, bg=CARD)
        row.pack(fill="x", pady=(8, 0))

        if vm.style == "bar":
            flap = FlapDisplay(row, tk, bg=CARD, font=self._mono_font(11),
                               tile_bg=TILE_BG, fg=FLAP_FG)
            flap.widget().pack(anchor="w")
            canvas = tk.Canvas(row, height=8, bg=CARD, highlightthickness=0)
            canvas.pack(fill="x", pady=(6, 4))
            c["canvas"] = canvas
            host = row
        else:
            canvas = tk.Canvas(row, width=72, height=72, bg=CARD, highlightthickness=0)
            canvas.pack(side="left")
            c["canvas"] = canvas
            info = tk.Frame(row, bg=CARD)
            info.pack(side="left", fill="x", expand=True, padx=12)
            flap = FlapDisplay(info, tk, bg=CARD, font=self._mono_font(11),
                               tile_bg=TILE_BG, fg=FLAP_FG)
            flap.widget().pack(anchor="w")
            host = info

        subrow = tk.Frame(host, bg=CARD)
        subrow.pack(fill="x")
        tk.Label(subrow, textvariable=sub_var, bg=CARD, fg=SUBTEXT,
                 font=("Segoe UI", 8), justify="left").pack(side="left")
        tk.Label(subrow, textvariable=reset_var, bg=CARD, fg=SUBTEXT,
                 font=("Segoe UI", 9)).pack(side="right")
        # Burn-rate / run-out / cost line + a 24h sparkline.
        foot = tk.Frame(host, bg=CARD)
        foot.pack(fill="x", pady=(3, 0))
        tk.Label(foot, textvariable=extra_var, bg=CARD, fg=SUBTEXT,
                 font=("Segoe UI", 8)).pack(side="left")
        if self.config.show_sparkline:
            spark = tk.Canvas(foot, width=120, height=16, bg=CARD, highlightthickness=0)
            spark.pack(side="right")
            c["spark"] = spark

        c["flap"] = flap
        # Reserve width with blank tiles so the cascade doesn't shift layout.
        flap.set_static(" " * max(1, len(vm.primary_text)))
        self._cards[vm.provider] = c
        self._attach_hover(c)
        self._attach_actions(c)
        self._draw_gauge(c, 0, vm.accent)
        self._update_extras(c)
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

        # Hovering the number flips it to the opposite metric (percent <-> amount).
        flap_w = c["flap"].widget()

        def num_enter(_):
            c["_hovering"] = True
            if c["provider"] not in self._animators and c.get("hover_text"):
                c["flap"].set_static(c["hover_text"])

        def num_leave(_):
            c["_hovering"] = False
            if c["provider"] not in self._animators:
                c["flap"].set_static(c["primary_text"])

        flap_w.bind("<Enter>", num_enter, add="+")
        flap_w.bind("<Leave>", num_leave, add="+")

    # --- click-through + context menu ----------------------------------
    def _attach_actions(self, c):
        tk = self.tk
        prov, url = c["provider"], c.get("usage_url")

        menu = tk.Menu(self.root, tearoff=0, bg=CARD, fg=TEXT,
                       activebackground=CARD_HOVER, activeforeground=TEXT, bd=0)
        if url:
            menu.add_command(label="Open usage page",
                             command=lambda u=url: webbrowser.open(u))
        menu.add_command(label="Copy amount", command=lambda p=prov: self._copy_amount(p))
        menu.add_command(label="Refresh now", command=lambda p=prov: self._refresh_card(p))

        def on_left(_):
            if url:
                webbrowser.open(url)

        def on_right(e):
            try:
                menu.tk_popup(e.x_root, e.y_root)
            finally:
                menu.grab_release()

        def walk(w):
            if not isinstance(w, tk.Button):  # don't hijack the ⟳ button
                w.bind("<Button-1>", on_left, add="+")
            w.bind("<Button-3>", on_right, add="+")
            for child in w.winfo_children():
                walk(child)

        walk(c["card"])

    def _copy_amount(self, prov: str):
        c = self._cards.get(prov)
        if c is None:
            return
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(c.get("primary_text", ""))
        except Exception:
            pass

    # --- per-card manual refresh ---------------------------------------
    def _refresh_card(self, prov: str):
        def work():
            status = self.engine.snapshot_one(prov)
            self.root.after(0, lambda: self._card_refreshed(prov, status))

        threading.Thread(target=work, daemon=True).start()

    def _card_refreshed(self, prov: str, status):
        self.statuses = [status if s.provider == prov else s for s in self.statuses]
        cfg = {c.name: c for c in self.config.providers}.get(prov)
        vm = build_card(status, cfg, self.config.display_metric, self.config.token_basis)
        c = self._cards.get(prov)
        if c is None:
            return
        c["accent"], c["primary_text"], c["hover_text"] = vm.accent, vm.primary_text, vm.hover_text
        c["ring_pct"] = vm.percent
        c["remaining"] = max(vm.limit - vm.used, 0) if vm.limit is not None else None
        c["sub_var"].set(("⚠ " + vm.error) if vm.error else "\n".join(vm.sub_lines))
        c["reset_var"].set(vm.reset_text or "")
        self._animators[prov] = {
            "kind": "reveal", "c": c, "text": vm.primary_text, "tpct": vm.percent or 0,
            "ring": vm.percent, "accent": vm.accent, "start": time.monotonic(),
            "dur": REVEAL_DUR,
        }
        self._ensure_anim_loop()
        self._update_extras(c)

    # --- burn-rate / run-out / cost / sparkline ------------------------
    def _update_extras(self, c):
        from . import analytics, pricing

        prov = c["provider"]
        parts: list[str] = []
        try:
            now = datetime.now(timezone.utc)
            samples = self.engine.ledger.samples_since(prov, now - timedelta(hours=24))
            if c.get("spark") is not None:
                # Plot cumulative consumption (a 24h trend), not the raw sawtooth.
                self._draw_spark(c["spark"], analytics.cumulative_series(samples), c["accent"])
            rate = analytics.burn_rate_per_hour(samples)
            if rate > 0:
                parts.append(analytics.human_rate(rate))
                ro = analytics.runout_text(c.get("remaining"), rate)
                if ro:
                    parts.append(ro)
            if self.config.show_cost:
                # The 30-day cost is a GROUP BY over usage_events — only changes
                # when new usage is recorded, so recompute it at most ~once/minute.
                mono = time.monotonic()
                if mono - c.get("_cost_at", -1e9) >= 60:
                    usages = self.engine.ledger.usage_since(prov, now - timedelta(days=30))
                    c["_cost_str"] = pricing.format_cost(pricing.cost_for_usage(usages))
                    c["_cost_at"] = mono
                if c.get("_cost_str"):
                    parts.append(f"≈ {c['_cost_str']}/30d")
        except Exception:
            pass
        c["extra_var"].set("  ·  ".join(parts))

    def _draw_spark(self, canvas, values, accent):
        from . import analytics

        try:
            canvas.delete("all")
            w = int(canvas["width"])
            h = int(canvas["height"])
            pts = analytics.spark_points([float(v) for v in values], w, h, pad=2)
            if len(pts) >= 2:
                flat = [coord for p in pts for coord in p]
                canvas.create_line(*flat, fill=accent, width=2, smooth=True)
        except Exception:
            pass

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

        from .relaunch import popen_kwargs, subprocess_args

        try:
            subprocess.Popen(subprocess_args("login", self.config_path), **popen_kwargs())
        except Exception as exc:  # pragma: no cover
            print(f"[token-counter] could not open login: {exc}")

    def _open_settings(self):
        SettingsDialog(self)

    def _relaunch(self):
        """Reopen the dashboard in a fresh process (e.g. after a theme change)."""
        import subprocess

        from .relaunch import popen_kwargs, subprocess_args

        self._save_geometry()
        try:
            subprocess.Popen(subprocess_args("window", self.config_path), **popen_kwargs())
        except Exception as exc:  # pragma: no cover
            print(f"[token-counter] could not relaunch: {exc}")
        self.root.after(150, self.root.destroy)

    def run(self):
        self.root.mainloop()


class SettingsDialog:
    """Tabbed settings: Display, Alerts, Startup, Data."""

    def __init__(self, dashboard: "Dashboard"):
        tk = dashboard.tk
        from tkinter import ttk

        self.tk = tk
        self.dash = dashboard
        self.cfg = dashboard.config
        top = tk.Toplevel(dashboard.root, bg=BG)
        self.top = top
        top.title("tokn — Settings")
        top.geometry("420x340")
        top.transient(dashboard.root)
        from .theme import apply_theme

        apply_theme(top)

        nb = ttk.Notebook(top)
        nb.pack(fill="both", expand=True, padx=8, pady=8)
        self._display_tab(nb)
        self._alerts_tab(nb)
        self._startup_tab(nb)
        self._data_tab(nb)

        ttk.Button(top, text="Close", command=top.destroy).pack(pady=(0, 10))

    # --- tabs ----------------------------------------------------------
    def _frame(self, nb, title):
        f = self.tk.Frame(nb, bg=BG, padx=14, pady=12)
        nb.add(f, text=title)
        return f

    def _display_tab(self, nb):
        tk = self.tk
        f = self._frame(nb, "Display")
        from tkinter import ttk

        tk.Label(f, text="Theme", bg=BG, fg=TEXT, font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self.theme_var = tk.StringVar(value=self.cfg.theme)
        ttk.Combobox(f, textvariable=self.theme_var, state="readonly", width=14,
                     values=["dark", "light", "system"]).pack(anchor="w", pady=(0, 8))
        self.theme_var.trace_add("write", lambda *a: self._on_theme())

        self._radio_group(f, "Show", "token_basis",
                          [("Tokens used", "used"), ("Tokens remaining", "remaining")],
                          self.cfg.token_basis, self._on_basis)
        self._radio_group(f, "As", "display_metric",
                          [("Amount", "amount"), ("Percentage", "percent")],
                          self.cfg.display_metric, self._on_metric)

        self.cost_var = tk.BooleanVar(value=self.cfg.show_cost)
        self.spark_var = tk.BooleanVar(value=self.cfg.show_sparkline)
        ttk.Checkbutton(f, text="Show estimated cost", variable=self.cost_var,
                        command=lambda: self._toggle("show_cost", self.cost_var)).pack(anchor="w", pady=(8, 0))
        ttk.Checkbutton(f, text="Show 24h sparkline + burn-rate", variable=self.spark_var,
                        command=lambda: self._toggle("show_sparkline", self.spark_var)).pack(anchor="w")
        tk.Label(f, text="Hover a number to see the other metric.", bg=BG, fg=SUBTEXT,
                 font=("Segoe UI", 8)).pack(anchor="w", pady=(8, 0))

    def _alerts_tab(self, nb):
        tk = self.tk
        from tkinter import ttk

        f = self._frame(nb, "Alerts")
        self.alerts_var = tk.BooleanVar(value=self.cfg.alerts_enabled)
        ttk.Checkbutton(f, text="Notify when a provider crosses a threshold",
                        variable=self.alerts_var,
                        command=lambda: self._toggle("alerts_enabled", self.alerts_var)).pack(anchor="w")
        tk.Label(f, text="Alert threshold (%)", bg=BG, fg=TEXT,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(10, 0))
        self.threshold_var = tk.IntVar(value=self.cfg.alert_threshold)
        scale = tk.Scale(f, from_=50, to=100, orient="horizontal", variable=self.threshold_var,
                         bg=BG, fg=TEXT, highlightthickness=0, troughcolor=CARD)
        # Persist once on release, not on every pixel of the drag.
        scale.bind("<ButtonRelease-1>", lambda e: self._on_threshold())
        scale.pack(fill="x")
        tk.Label(f, text="The tray icon also tints amber/red as usage rises.",
                 bg=BG, fg=SUBTEXT, font=("Segoe UI", 8)).pack(anchor="w", pady=(6, 0))

    def _startup_tab(self, nb):
        tk = self.tk
        from tkinter import ttk

        f = self._frame(nb, "Startup")
        self.startup_var = tk.BooleanVar(value=startup_mod.is_enabled())
        ttk.Checkbutton(f, text="Open tokn on Windows startup", variable=self.startup_var,
                        command=self._toggle_startup).pack(anchor="w")
        self.status = tk.Label(f, text=self._startup_status(), bg=BG, fg=SUBTEXT,
                               font=("Segoe UI", 8), anchor="w", wraplength=360, justify="left")
        self.status.pack(anchor="w", pady=(6, 0))
        tk.Label(f, text=f"Refreshes every {self.cfg.refresh_seconds}s.", bg=BG, fg=SUBTEXT,
                 font=("Segoe UI", 9)).pack(anchor="w", pady=(10, 0))

    def _data_tab(self, nb):
        tk = self.tk
        from tkinter import ttk

        f = self._frame(nb, "Data")
        tk.Label(f, text="Export recorded usage (CSV/JSON):", bg=BG, fg=TEXT).pack(anchor="w")
        row = tk.Frame(f, bg=BG)
        row.pack(anchor="w", pady=8)
        ttk.Button(row, text="Export CSV…", command=lambda: self._export("csv")).pack(side="left")
        ttk.Button(row, text="Export JSON…", command=lambda: self._export("json")).pack(side="left", padx=8)
        tk.Label(f, text="Includes per-model tokens + approximate cost for the last 30 days.",
                 bg=BG, fg=SUBTEXT, font=("Segoe UI", 8), wraplength=360,
                 justify="left").pack(anchor="w")

    # --- helpers -------------------------------------------------------
    def _radio_group(self, parent, label, key, options, current, handler):
        tk = self.tk
        from tkinter import ttk

        tk.Label(parent, text=label, bg=BG, fg=TEXT,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(6, 0))
        var = tk.StringVar(value=current)
        setattr(self, f"{key}_var", var)
        rowf = tk.Frame(parent, bg=BG)
        rowf.pack(anchor="w")
        for text, value in options:
            ttk.Radiobutton(rowf, text=text, value=value, variable=var,
                            command=lambda v=value: handler(v)).pack(side="left", padx=(0, 10))

    def _save(self, key, value):
        from .config import save_setting

        try:
            save_setting(self.dash.config_path, key, value)
        except Exception:
            pass
        setattr(self.cfg, key, value)

    def _toggle(self, key, var):
        self._save(key, bool(var.get()))
        self.dash._build_cards()

    def _on_basis(self, value):
        self._save("token_basis", value)
        self.dash._build_cards()

    def _on_metric(self, value):
        self._save("display_metric", value)
        self.dash._build_cards()

    def _on_threshold(self):
        self._save("alert_threshold", int(self.threshold_var.get()))

    def _on_theme(self):
        value = self.theme_var.get()
        if value == self.cfg.theme:
            return
        self._save("theme", value)
        self.dash._relaunch()  # reopen so the new palette paints everything

    def _export(self, fmt):
        from tkinter import filedialog

        from .reporting import export_usage

        path = filedialog.asksaveasfilename(
            parent=self.top, defaultextension=f".{fmt}",
            filetypes=[(fmt.upper(), f"*.{fmt}")], title=f"Export usage as {fmt.upper()}",
        )
        if not path:
            return
        start = datetime.now(timezone.utc) - timedelta(days=30)
        names = [p.name for p in self.cfg.providers]
        try:
            Path(path).write_text(export_usage(self.dash.engine.ledger, names, start, fmt),
                                  encoding="utf-8")
        except Exception as exc:  # pragma: no cover
            print(f"[token-counter] export failed: {exc}")

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
        try:
            save_open_on_startup(self.dash.config_path, value)
        except Exception:
            pass
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
        self._pinned = bool(state_mod.get("compact_pinned", False))
        self.root.attributes("-topmost", True)
        self._photos: list = []

        self._rows: dict = {}
        self._row_keys: list = []
        self._animators: dict = {}
        self._anim_running = False
        self._save_job = None

        self.frame = tk.Frame(self.root, bg=CARD, padx=10, pady=8)
        self.frame.pack(padx=1, pady=1)
        self._build()
        self._position()
        self._start_cascade()
        self.root.bind("<FocusOut>", self._on_focus_out)
        self.root.bind("<Escape>", lambda e: (None if self._pinned else self.root.destroy()))
        self.root.bind("<Configure>", self._on_configure)
        self.root.after(max(5, config.refresh_seconds) * 1000, self._refresh)

    def _on_focus_out(self, _e):
        if not self._pinned:
            self.root.destroy()

    def _on_configure(self, _e):
        if self._save_job is not None:
            try:
                self.root.after_cancel(self._save_job)
            except Exception:
                pass
        self._save_job = self.root.after(500, self._save_geometry)

    def _save_geometry(self):
        try:
            state_mod.set("compact_geometry", self.root.geometry())
        except Exception:
            pass

    def _toggle_pin(self):
        self._pinned = not self._pinned
        state_mod.set("compact_pinned", self._pinned)
        self.root.attributes("-topmost", True)
        self._build()
        self._start_cascade()

    def _mono_font(self, size=10, weight="bold"):
        from .fonts import app_font_family

        return (app_font_family(), size, weight)

    def _build(self):
        for w in self.frame.winfo_children():
            w.destroy()
        self._rows = {}
        tk = self.tk
        # Header with pin (and a close button while pinned, since there's no titlebar).
        head = tk.Frame(self.frame, bg=CARD)
        head.pack(fill="x")
        tk.Label(head, text="tokn", bg=CARD, fg=SUBTEXT,
                 font=("Segoe UI", 8, "bold")).pack(side="left")
        if self._pinned:
            tk.Button(head, text="✕", bg=CARD, fg=SUBTEXT, relief="flat", bd=0,
                      activebackground=CARD_HOVER, cursor="hand2",
                      command=self.root.destroy).pack(side="right")
        tk.Button(head, text=("📌" if self._pinned else "📍"), bg=CARD,
                  fg=(TEXT if self._pinned else SUBTEXT), relief="flat", bd=0,
                  activebackground=CARD_HOVER, cursor="hand2",
                  command=self._toggle_pin).pack(side="right", padx=(0, 4))

        rows: list[CompactVM] = build_compact(
            self.engine.snapshot(), self.config.providers,
            metric=self.config.display_metric, basis=self.config.token_basis)
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
                               tile_w=9, tile_h=16, tile_bg=TILE_BG, fg=SUBTEXT)
            flap.widget().pack(side="right")
            flap.set_static(" " * max(1, len(vm.primary_text)))
            bar = tk.Canvas(self.frame, height=5, width=260, bg=CARD, highlightthickness=0)
            bar.pack(fill="x")
            row = {"flap": flap, "bar": bar, "text": vm.primary_text,
                   "hover_text": vm.hover_text, "pct": vm.percent, "accent": vm.accent}
            self._rows[vm.provider] = row
            self._attach_row_hover(flap, row)
            _draw_bar(bar, 0, 0, 260, 5, 0, vm.accent)

    def _attach_row_hover(self, flap, row):
        w = flap.widget()

        def enter(_):
            row["_hovering"] = True
            if row.get("hover_text"):
                flap.set_static(row["hover_text"])

        def leave(_):
            row["_hovering"] = False
            flap.set_static(row["text"])

        w.bind("<Enter>", enter, add="+")
        w.bind("<Leave>", leave, add="+")

    def _refresh(self):
        rows: list[CompactVM] = build_compact(
            self.engine.snapshot(), self.config.providers,
            metric=self.config.display_metric, basis=self.config.token_basis)
        if [vm.provider for vm in rows] != self._row_keys:
            self._build()
            self._start_cascade()
        else:
            for vm in rows:  # quiet update
                row = self._rows.get(vm.provider)
                if row is None or vm.provider in self._animators:
                    continue
                if vm.primary_text != row["text"]:
                    shown = vm.hover_text if row.get("_hovering") and vm.hover_text else vm.primary_text
                    row["flap"].set_static(shown)
                    row["text"] = vm.primary_text
                row["hover_text"] = vm.hover_text
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
        saved = state_mod.get("compact_geometry")
        if saved:  # remembered position (and size) from last time
            try:
                self.root.geometry(saved)
                self.root.update_idletasks()
                self._clamp_on_screen()  # never restore off-screen (would be unclosable when pinned)
                if not self._pinned:
                    self.root.focus_force()
                return
            except Exception:
                pass
        w, h = self.root.winfo_width(), self.root.winfo_height()
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(f"+{sw - w - 20}+{sh - h - 60}")
        self.root.focus_force()

    def _clamp_on_screen(self):
        """Keep the borderless popup fully on-screen so its ✕ is always reachable."""
        self.root.update_idletasks()
        w, h = self.root.winfo_width(), self.root.winfo_height()
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        x = min(max(self.root.winfo_x(), 0), max(0, sw - w))
        y = min(max(self.root.winfo_y(), 0), max(0, sh - h))
        self.root.geometry(f"+{x}+{y}")

    def run(self):
        self.root.mainloop()


def run_dashboard(config_path: str | Path) -> None:
    config = load_config(config_path)
    Dashboard(config, str(Path(config_path).expanduser())).run()


def run_compact(config_path: str | Path) -> None:
    config = load_config(config_path)
    CompactPopup(config, str(Path(config_path).expanduser())).run()
