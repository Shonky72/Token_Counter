"""The default config written on first run.

Baked into the app (and the .exe) so a friend can run the bare executable with
nothing set up: on first launch this is written to ~/.token_counter/config.yaml,
the sign-in window opens, and they paste their own keys. Credentials live in
*their* keyring, so the same .exe is safe to share.
"""

from __future__ import annotations

DEFAULT_CONFIG_YAML = """\
# tokn configuration. Created automatically on first run.
# Edit freely, then restart tokn to apply changes.

refresh_seconds: 30          # how often the gauges refresh (seconds)
open_on_startup: false       # also toggleable from the tray / Settings
view_mode: dashboard         # what the tray icon opens: dashboard | compact
ledger_path: "~/.token_counter/ledger.db"

server:
  enabled: true
  host: "127.0.0.1"
  port: 8787

providers:
  # Claude — live provider-enforced rate limits from response headers.
  - name: claude
    type: rate_limit
    scheme: anthropic
    display_name: Claude
    display: ring
    primary: requests

  # ChatGPT / OpenAI — same live enforced limits.
  - name: openai
    type: rate_limit
    scheme: openai
    display_name: ChatGPT
    display: ring
    primary: tokens

  # Gemini — Google exposes no live remaining-limit headers, so this tracks
  # usage you report against an allowance you choose.
  - name: gemini
    type: gemini
    display_name: Gemini
    display: bar
    budget:
      period: monthly
      limit: 2000000
"""
