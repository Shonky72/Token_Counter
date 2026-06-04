# Token Counter

A Windows system-tray widget that shows a **live, per-model count of tokens used
vs. remaining** against an allowance you set — for Claude, Gemini, or any
provider you add. Hover the tray icon for the totals; right-click for the
per-model breakdown. Refreshes every 30 seconds.

```
Token Counter
claude (monthly): 620K/1.0M · 380K left (62%)
gemini (monthly): 90K/2.0M · 1.9M left (5%)
```

The tray icon fills up and changes color as you burn through the budget
(green → amber → red).

---

## How token tracking works (read this first)

You asked for an **accurate, live (within 30s) count of tokens used vs. remaining
per model**. The honest reality across providers:

- **There is no universal, live, per-model "tokens remaining" API.** Provider
  usage APIs (Anthropic, Google) lag by minutes and need admin credentials, and
  the "remaining" number depends on a limit *you* define, not one they expose.

So Token Counter is built around a **local usage ledger** that *you* feed:

1. You configure an allowance per provider/model (e.g. `1,000,000` tokens/month).
2. Your code reports each call's token usage to a tiny local endpoint
   (`http://127.0.0.1:8787/usage`) — one line after each LLM response.
3. The tray sums usage for the current period and shows **used / limit /
   remaining**, live within one refresh.

This is exact, truly live, and works for **any provider you choose** — that's the
`local_ledger` (and `gemini`) provider type. An optional `anthropic_admin`
provider is included to *pull* usage from Anthropic's Usage API instead, if you
prefer official numbers and can tolerate the lag.

---

## Install

```bash
git clone <this repo>
cd Token_Counter
python -m pip install -e .
```

Then create your config:

```bash
mkdir -p ~/.token_counter
cp config.example.yaml ~/.token_counter/config.yaml   # edit limits to taste
```

## Run

```bash
token-counter run
```

A tray icon appears. Hover for the summary; right-click for per-model detail,
"Refresh now", and "Quit". The local usage server starts automatically.

Headless check (no tray) — handy for testing:

```bash
token-counter status
```

## Reporting usage from your code

Copy [`examples/report_usage.py`](examples/report_usage.py) into your project and
call `report(...)` after each LLM response:

```python
from report_usage import report

msg = client.messages.create(model="claude-opus-4-8", max_tokens=1024,
                             messages=[{"role": "user", "content": "Hi"}])
report("claude", "claude-opus-4-8",
       input_tokens=msg.usage.input_tokens,
       output_tokens=msg.usage.output_tokens)
```

Or record manually from the CLI:

```bash
token-counter record --provider claude --model claude-opus-4-8 --input 1200 --output 340
```

---

## Configuration

`~/.token_counter/config.yaml` (see [`config.example.yaml`](config.example.yaml)):

| Key                       | Meaning                                              |
| ------------------------- | ---------------------------------------------------- |
| `refresh_seconds`         | Tray refresh interval (30 = "live within 30s")       |
| `ledger_path`             | Where the SQLite usage ledger is stored              |
| `server.{host,port}`      | Local usage-reporting endpoint                       |
| `providers[].name`        | Display name in the tray                             |
| `providers[].type`        | `local_ledger` \| `gemini` \| `anthropic_admin`      |
| `providers[].budget`      | `period` (daily/weekly/monthly/total), `limit`, `per_model` |

`token-counter providers` lists the registered types.

---

## Adding a provider ("any I choose")

Providers are plugins. To add one:

1. Create `src/token_counter/providers/myprovider.py`:

   ```python
   from datetime import datetime
   from .base import Provider, register
   from ..models import ModelUsage, ProviderUsage

   @register("myprovider")
   class MyProvider(Provider):
       def get_usage(self, window_start: datetime) -> ProviderUsage:
           # Either read self.ledger.usage_since(self.name, window_start)
           # for live local tracking, or pull from your provider's API here.
           models = self.ledger.usage_since(self.name, window_start)
           return ProviderUsage(provider=self.name, models=models)
   ```

2. Import it in `src/token_counter/providers/__init__.py`.
3. Reference `type: myprovider` in your config.

`gemini.py` is a fully worked template for exactly this (live ledger by default,
with a marked extension point for a Cloud Monitoring "pull" integration).

---

## Package as a standalone Windows .exe

```bash
python -m pip install pyinstaller
pyinstaller --noconsole --onefile --name TokenCounter ^
    --collect-all pystray --collect-all PIL ^
    src/token_counter/__main__.py
```

Drop the resulting `dist/TokenCounter.exe` into your Startup folder
(`shell:startup`) so the widget launches with Windows.

---

## Tests

```bash
python -m pytest
```

Core logic (config, ledger, engine, rendering, server) is covered and runs
headless — no tray or display required.

## Project layout

```
src/token_counter/
  config.py        # YAML config + budget-period windows
  ledger.py        # SQLite usage ledger (the live source of truth)
  models.py        # dataclasses passed between layers
  engine.py        # config + ledger -> BudgetStatus list
  render.py        # tooltip / detail text formatting
  server.py        # localhost usage-reporting HTTP endpoint
  tray.py          # pystray tray icon (Windows)
  app.py           # CLI: run / status / record / providers
  providers/
    base.py            # Provider ABC + registry
    local_ledger.py    # live, exact, provider-agnostic
    gemini.py          # template for a new provider
    anthropic_admin.py # optional pull from Anthropic Usage API
```
