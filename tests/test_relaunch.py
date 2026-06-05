import sys

from token_counter import relaunch
from token_counter.app import build_parser


def test_config_flag_precedes_subcommand(monkeypatch):
    # The bug: -c was placed AFTER the subcommand, which argparse rejects.
    monkeypatch.setattr(relaunch.sys, "frozen", False, raising=False)
    args = relaunch.subprocess_args("login", "/p/cfg.yaml")
    # -c <path> must come immediately before the command.
    assert args[-3:] == ["-c", "/p/cfg.yaml", "login"]
    assert "-m" in args  # source mode


def test_frozen_mode_omits_module_flag(monkeypatch):
    monkeypatch.setattr(relaunch.sys, "frozen", True, raising=False)
    args = relaunch.subprocess_args("window", "/p/cfg.yaml")
    assert args == [sys.executable, "-c", "/p/cfg.yaml", "window"]
    monkeypatch.delattr(relaunch.sys, "frozen", raising=False)


def test_no_config_path():
    args = relaunch.subprocess_args("popup")
    assert args[-1] == "popup"
    assert "-c" not in args


def test_parser_accepts_produced_argument_order():
    # The produced tail must actually parse without "unrecognized arguments".
    parser = build_parser()
    ns = parser.parse_args(["-c", "/p/cfg.yaml", "login"])
    assert ns.command == "login"
    assert ns.config == "/p/cfg.yaml"
