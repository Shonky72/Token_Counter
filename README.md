# Token Counter

A Windows system-tray widget that shows a **live count of tokens used vs.
remaining against the limits your AI provider actually enforces** — read
straight from each provider's own API responses, not numbers you type in. Hover
the tray icon for the totals; right-click for the per-window breakdown and the
**sign-in screen**. Refreshes every 30 seconds.

```
Token Counter
claude · tokens/min: 28K/40K · 12K left (70%) · resets in 41s
openai · tokens/min: 500/90K · 89.5K left (1%) · resets in 359s
```

The tray icon fills and changes color as you approach the limit
(green → amber → red).

---

## What "provider-enforced limit" means here

Every Anthropic and OpenAI API response carries **rate-limit headers** — the
per-minute token/request `limit`, `remaining`, and `reset` that your account
tier enforces. Token Counter reads those directly, so the gauge is the
provider's real enforced limit, live, with a reset countdown. Nothing is
hand-configured.

How the headers get to the widget (zero extra cost): your code forwards each
response's headers to a tiny local endpoint after each call. One line:

```python
from report_usage import report_ratelimit

raw = client.messages.with_raw_response.create(model="claude-opus-4-8",
        max_tokens=1024, messages=[{"role": "user", "content": "Hi"}])
report_ratelimit("claude", dict(raw.headers))   # tray now shows live limit/remaining
```

The tray shows the last captured `remaining` and counts down to `reset`; once
the window resets it rolls back to full. Want idle-time refresh without your own
traffic? Set `probe: true` on the provider to actively hit the provider's
`/models` endpoint each refresh.

> **Provider notes.** Anthropic & OpenAI return live rate-limit headers — full
> support. **Google/Gemini does not** expose live per-request remaining limits,
> so the `gemini` provider tracks usage you report against an allowance you set
> (or, if you run Vertex AI, you can extend it to pull Cloud Monitoring metrics).

---

## Login screen

`token-counter login` (or right-click the tray → **Accounts / Login…**) opens a
sign-in window. Per provider you get **both** methods:

- **API key** — paste it and click *Validate & Save*. The app makes a live probe
  call to confirm the key works, then stores it in **Windows Credential
  Manager** (via `keyring`; a permission-locked local file is the fallback).
- **OAuth** — click *Sign in with OAuth* (for providers with an `oauth:` block in
  config, e.g. Google). Your browser opens, you authorize, and the token is
  captured via a localhost redirect (Authorization Code + PKCE) and stored.

> There is **no** username/password-into-the-web-account option — AI providers
> don't allow logging into a consumer Claude.ai/Gemini account programmatically.
> API keys and OAuth are the supported credentials, which is what this screen
> uses.

---

## Install

```bash
git clone <this repo>
cd Token_Counter
python -m pip install -e .

mkdir -p ~/.token_counter
cp config.example.yaml ~/.token_counter/config.yaml   # edit providers
```

## Run

```bash
token-counter run             # tray + local server; opens login if not signed in
token-counter window          # the dashboard window (cards, rings/bars)
token-counter popup           # the compact hover-style summary
token-counter login           # the sign-in window
token-counter startup enable  # launch on Windows startup (also: disable | status)
token-counter shortcut        # create a Desktop shortcut (Windows)
token-counter icon icon.ico   # write the app icon as a .ico
token-counter uninstall       # remove startup entry, shortcut, and saved keys
token-counter status          # headless: print current limits/usage
token-counter providers       # list registered provider plugin types
```

Left-clicking the tray icon opens the dashboard; right-click gives **Open
dashboard**, **Compact view**, **Accounts / Login…**, an **Open on startup**
checkbox, **Refresh now**, and **Quit**.

### Dashboard & compact views

The dashboard mirrors a card per provider — a ring (or bar) gauge, the
`used / limit` count (`1.7M / 2.0M tokens`, or `12 / 45 messages` for
request limits), input/output sub-lines, and a live "Resets in 14m" countdown.
Each provider's look is configurable:

```yaml
- name: claude
  type: rate_limit
  scheme: anthropic
  display_name: Claude      # card title
  display: ring             # ring | bar
  primary: requests         # which window headlines the card ("messages")
  color: "#d97757"          # optional accent override
```

The compact view is the same data as a small always-on-top popup near the tray.

### Open on startup

Toggle it from the tray menu, the dashboard's ⚙ Settings, or the CLI
(`token-counter startup enable`). On Windows this adds a per-user
`HKCU\…\Run` entry that launches the tray with `pythonw` (no console window) —
no admin rights needed. The choice is mirrored into `open_on_startup` in your
config so it survives reinstalls.

### Sign in once — credentials are remembered

API keys and OAuth tokens are saved in the OS keyring (Windows Credential
Manager) the first time you sign in, and read back automatically on every
launch. You never retype them after a reboot. Providers resolve their key
straight from the keyring, so no environment-variable wiring is required.

## Reporting headers from your code

Copy [`examples/report_usage.py`](examples/report_usage.py) into your project:

- `report_ratelimit(provider, headers)` — forward response headers (live limits).
- `report_call(provider, headers, model, input_tokens=..., output_tokens=...)` —
  forward headers **and** token counts in one call.

Both are best-effort; failures never break your app.

---

## Configuration

`~/.token_counter/config.yaml` (see [`config.example.yaml`](config.example.yaml)):

| Key                        | Meaning                                                     |
| -------------------------- | ---------------------------------------------------------- |
| `refresh_seconds`          | Tray refresh interval (30 = "live within 30s")             |
| `ledger_path`              | SQLite store for usage + captured rate-limit snapshots     |
| `server.{host,port}`       | Local endpoint your code forwards headers/usage to         |
| `providers[].name`         | Display name in the tray                                    |
| `providers[].type`         | `rate_limit` \| `gemini` \| `local_ledger` \| `anthropic_admin` |
| `providers[].scheme`       | `anthropic` \| `openai` \| `google` \| `auto` (for `rate_limit`) |
| `providers[].api_key_env`  | Env var to receive the stored key (so it stays in the keyring) |
| `providers[].probe`        | `true` to actively refresh limits each tick (optional)     |
| `providers[].oauth`        | OAuth client block (`client_id`, `client_secret`, `preset: google`, …) |
| `providers[].budget`       | Only for ledger-based providers: `period`, `limit`, `per_model` |

---

## Adding a provider ("any I choose")

Providers are plugins. Most providers that return standard rate-limit headers
work with `type: rate_limit` and the right `scheme` — no code needed. For a
provider with a different shape:

1. Create `src/token_counter/providers/myprovider.py`:

   ```python
   from datetime import datetime
   from .base import Provider, register
   from ..models import Gauge, ProviderStatus

   @register("myprovider")
   class MyProvider(Provider):
       auth_methods = ("api_key", "oauth")   # what the login screen offers
       def poll(self, now=None) -> ProviderStatus:
           # read a captured snapshot, or pull from the provider's API here
           snap = self.ledger.get_rate_limits(self.name)
           ...
           return ProviderStatus(self.name, gauges=[Gauge("tokens/min", used, limit)])
       def validate_credential(self, secret):   # for the login screen
           return bool(secret), "saved"
   ```

2. Import it in `src/token_counter/providers/__init__.py`.
3. Reference `type: myprovider` in your config.

`rate_limit.py` (live headers) and `gemini.py` (ledger + Cloud Monitoring
extension point) are the two worked templates.

---

## Package as a standalone Windows .exe (shareable)

> **Your friends do NOT need Python.** The built `TokenCounter.exe` bundles
> Python and everything else inside it — it's one self-contained file. Only
> *building* needs Python, and even that can be done for you (see "Get it
> without building" below).

**Easiest:** double-click **`build.bat`**. It installs what's needed and produces
`dist\TokenCounter.exe` — one file you can copy anywhere or send to friends.

### Get it without building (GitHub Actions)

So nobody needs Python at all: the repo includes a workflow
(`.github/workflows/build-windows.yml`) that builds `TokenCounter.exe` **and**
the `.msi` on a Windows runner every push. Open the **Actions** tab → the latest
run → download the **TokenCounter-exe** artifact. Share that file. Tagging a
release also attaches both to the release page.

Equivalent manual command:

```bat
python -m pip install -e . pyinstaller
python -m PyInstaller --noconsole --onefile --name TokenCounter --paths src ^
    --collect-all pystray --collect-all PIL --collect-all keyring ^
    run_token_counter.py
```

`build.bat` also embeds the app icon into the `.exe`, drops a **"Token Counter"
shortcut on your Desktop**, and offers to launch the app when it finishes.

### Build a .msi installer

For a "proper" installer (Start Menu + Desktop shortcuts, shows up in Add/Remove
Programs), double-click **`build_msi.bat`**. It uses
[cx_Freeze](https://cx-freeze.readthedocs.io) to produce:

```
dist\TokenCounter-0.1.0-win64.msi
```

Double-click that `.msi` to install. It's a **per-user install (no admin
prompt)** to `%LOCALAPPDATA%\Programs\TokenCounter`, and uninstalls from
Windows Settings → Apps like any normal program. Share the single `.msi` with
friends — each person enters their own API keys after installing.

To install **system-wide** instead (all users, requires admin), edit
`setup_msi.py`: set `all_users` to `True` and `initial_target_dir` to
`r"[ProgramFilesFolder]\TokenCounter"`.

> `.msi` vs the bare `.exe`: the `.exe` from `build.bat` is one portable file you
> can copy anywhere; the `.msi` is a real installer that registers the app with
> Windows. Both run the exact same program — pick whichever you prefer to share.

### Uninstalling

Double-click **`uninstall.bat`** (or run `token-counter uninstall`). It removes
the startup entry, the Desktop shortcut, and your saved API keys — without
touching the program files. Add `--purge` to also delete the
`~/.token_counter` config/ledger folder, or `--keep-keys` to leave credentials
in place.

**Sharing with friends:** send them just `TokenCounter.exe`. On first run it
writes a default config to `~/.token_counter/config.yaml` and opens the sign-in
window automatically — each person enters **their own** API keys, which are
saved in **their own** Windows Credential Manager. Nothing of yours travels with
the file. (Windows SmartScreen may warn about an unsigned app the first time —
*More info → Run anyway*.)

### Icon & provider logos

The tray icon is a live **usage meter** — ascending bars that light up and shift
green → amber → red as you approach your limit — generated in code (no image
files to ship). The same motif is the window/`.exe` icon.

Provider cards show a logo. Because the official ChatGPT/Claude/Gemini marks are
trademarked, the app ships clean **brand-style glyphs** drawn in code (OpenAI
ring, Claude sunburst, Gemini sparkle). To use the real logos, drop a PNG at
`~/.token_counter/logos/<provider>.png` (e.g. `claude.png`) and it's picked up
automatically.

## If something goes wrong

If the app seems to run (it's in Task Manager) but no tray icon or window
appears, check the log file it writes on every launch:

```
%USERPROFILE%\.token_counter\token_counter.log
```

Any startup error is recorded there (and shown in a popup). Send me that file's
contents and I can pinpoint the cause.

## Tests

```bash
python -m pytest
```

65 tests cover config, ledger, rate-limit header parsing, providers, the engine,
rendering, the view-model (cards/compact), startup plumbing, the HTTP server,
credential storage, and the OAuth PKCE/redirect logic — all headless (no
tray/browser/display required).

## Project layout

```
src/token_counter/
  config.py        # YAML config + budget windows
  ledger.py        # SQLite: usage events + rate-limit snapshots
  ratelimit.py     # parse Anthropic/OpenAI rate-limit headers
  models.py        # Gauge / ProviderStatus dataclasses
  probe.py         # cheap credential-probe calls
  engine.py        # build providers, poll them
  render.py        # tooltip / detail text
  server.py        # localhost /usage + /ratelimit endpoints
  auth.py          # keyring-backed credential store (remembered sign-in)
  oauth.py         # OAuth Authorization Code + PKCE (loopback)
  startup.py       # launch-on-Windows-startup (HKCU Run key)
  shortcut.py      # create a Desktop shortcut (PowerShell)
  icons.py         # ascending-bars app icon + live tray usage meter
  logos.py         # provider logos (glyphs, or your PNGs if present)
  viewmodel.py     # dashboard/compact presentation model (pure, tested)
  login_ui.py      # Tkinter sign-in window (API key + OAuth)
  window_ui.py     # Tkinter dashboard + compact popup (cards, logos, gauges)
  tray.py          # pystray tray icon (Windows)
  app.py           # CLI: run / window / popup / login / startup / shortcut / …
  providers/
    base.py            # Provider ABC + registry
    rate_limit.py      # provider-enforced live limits (Anthropic/OpenAI)
    gemini.py          # template (ledger + Cloud Monitoring hook)
    local_ledger.py    # manual allowance vs. ledger usage
    anthropic_admin.py # optional Anthropic Usage API (billing view)
```
