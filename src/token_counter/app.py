"""Command-line entry points.

    token-counter run      [-c config.yaml]   # tray widget + usage/ratelimit server
    token-counter login    [-c config.yaml]   # open the sign-in window
    token-counter status   [-c config.yaml]   # print current usage (headless)
    token-counter record   --provider claude --model claude-opus-4-8 \
                           --input 1200 --output 340
    token-counter providers                    # list registered provider types
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .auth import CredentialStore, load_credentials_into_env
from .config import ConfigError, load_config
from .engine import Engine
from .ledger import Ledger
from .providers import registered_types
from .render import detail_text

DEFAULT_CONFIG = "~/.token_counter/config.yaml"


def _load(path: str):
    config = load_config(path)
    ledger = Ledger(config.resolved_ledger_path)
    store = CredentialStore()
    # Make stored API keys available to providers that use api_key_env, too.
    load_credentials_into_env(store, config.providers)
    return config, ledger, store


def _cmd_run(args) -> int:
    from . import startup as startup_mod
    from .server import UsageServer
    from .tray import TrayApp

    config, ledger, store = _load(args.config)

    # Honor the saved "open on startup" preference (Windows registry).
    if startup_mod.is_supported() and config.open_on_startup and not startup_mod.is_enabled():
        startup_mod.enable()

    # First-run nudge: if nothing is signed in, open the login window.
    if config.providers and not any(store.has_any(p.name) for p in config.providers):
        print("[token-counter] no credentials found — opening the login window.")
        import subprocess

        from .relaunch import subprocess_args

        subprocess.Popen(subprocess_args("login", args.config))

    server = None
    if config.server.enabled:
        server = UsageServer(config.server, ledger)
        server.start()
        print(f"[token-counter] usage/ratelimit server listening on {server.address}")

    engine = Engine(config, ledger, store)
    app = TrayApp(
        engine,
        refresh_seconds=config.refresh_seconds,
        server=server,
        config_path=str(Path(args.config).expanduser()),
        default_view=config.view_mode,
    )
    print("[token-counter] tray started; click the icon for the dashboard.")
    app.run()
    return 0


def _cmd_login(args) -> int:
    from .login_ui import run_login

    run_login(args.config)
    return 0


def _cmd_window(args) -> int:
    from .window_ui import run_dashboard

    run_dashboard(args.config)
    return 0


def _cmd_popup(args) -> int:
    from .window_ui import run_compact

    run_compact(args.config)
    return 0


def _cmd_startup(args) -> int:
    from . import startup as startup_mod
    from .config import save_open_on_startup

    if not startup_mod.is_supported():
        print("[token-counter] open-on-startup is only supported on Windows.")
        return 1
    if args.action == "status":
        print("enabled" if startup_mod.is_enabled() else "disabled")
        return 0
    enable = args.action == "enable"
    ok = startup_mod.set_enabled(enable)
    try:
        save_open_on_startup(args.config, enable)
    except Exception:
        pass
    print(f"[token-counter] startup {'enabled' if enable else 'disabled'}"
          + ("" if ok else " (registry update failed)"))
    return 0 if ok else 1


def _cmd_status(args) -> int:
    config, ledger, store = _load(args.config)
    engine = Engine(config, ledger, store)
    print(detail_text(engine.snapshot()))
    return 0


def _cmd_record(args) -> int:
    config, ledger, store = _load(args.config)
    ledger.record(
        provider=args.provider,
        model=args.model,
        input_tokens=args.input,
        output_tokens=args.output,
        cache_read_tokens=args.cache_read,
        cache_creation_tokens=args.cache_creation,
    )
    print(
        f"[token-counter] recorded {args.input + args.output} tokens "
        f"for {args.provider}/{args.model}"
    )
    return 0


def _cmd_providers(args) -> int:
    print("Registered provider types:")
    for t in registered_types():
        print(f"  - {t}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="token-counter", description=__doc__)
    parser.add_argument("-c", "--config", default=DEFAULT_CONFIG, help="path to config file")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("run", help="start the tray widget").set_defaults(func=_cmd_run)
    sub.add_parser("window", help="open the dashboard window").set_defaults(func=_cmd_window)
    sub.add_parser("popup", help="open the compact summary popup").set_defaults(func=_cmd_popup)
    sub.add_parser("login", help="open the provider sign-in window").set_defaults(func=_cmd_login)
    sub.add_parser("status", help="print current usage and exit").set_defaults(func=_cmd_status)
    sub.add_parser("providers", help="list registered provider types").set_defaults(
        func=_cmd_providers
    )

    st = sub.add_parser("startup", help="manage launch-on-Windows-startup")
    st.add_argument("action", choices=["enable", "disable", "status"])
    st.set_defaults(func=_cmd_startup)

    rec = sub.add_parser("record", help="record a usage event into the ledger")
    rec.add_argument("--provider", required=True)
    rec.add_argument("--model", required=True)
    rec.add_argument("--input", type=int, default=0)
    rec.add_argument("--output", type=int, default=0)
    rec.add_argument("--cache-read", type=int, default=0)
    rec.add_argument("--cache-creation", type=int, default=0)
    rec.set_defaults(func=_cmd_record)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        args.command = "run"
        args.func = _cmd_run

    if args.command == "providers":
        return _cmd_providers(args)

    try:
        return args.func(args)
    except ConfigError as exc:
        print(f"[token-counter] config error: {exc}", file=sys.stderr)
        if not Path(args.config).expanduser().exists():
            print(
                f"  Hint: copy config.example.yaml to {args.config} and edit it.",
                file=sys.stderr,
            )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
