"""The default config written on first run.

Baked into the app (and the .exe) so a friend can run the bare executable with
nothing set up: on first launch this is written to ~/.token_counter/config.yaml,
the sign-in window opens, and they paste their own keys. Credentials live in
*their* keyring, so the same .exe is safe to share.
"""

from __future__ import annotations

DEFAULT_CONFIG_YAML = """\
# tokn configuration. Created automatically on first run.
# Add AI services from the login window (tray → Accounts / Login…), which writes
# them here for you. Edit freely; restart tokn to apply manual changes.

refresh_seconds: 30          # how often the gauges refresh (seconds)
open_on_startup: false       # also toggleable from the tray / Settings
view_mode: dashboard         # what the tray icon opens: dashboard | compact
ledger_path: "~/.token_counter/ledger.db"

server:
  enabled: true
  host: "127.0.0.1"
  port: 8787

# Empty until you add services in the login window.
providers: []
"""
