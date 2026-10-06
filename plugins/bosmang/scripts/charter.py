#!/usr/bin/env python3
"""SessionStart hook: render the standing orders and hand them to Claude Code as context.

Runs on every session start, including after /clear and compaction, which is the point:
the orders are re-read rather than remembered.

Config is JSON at $BOSMANG_CONFIG, else ~/.config/bosmang/config.json. Every key is optional:

  owner             who the crew works for                  (default "the human")
  coordinator       the coordinator session's name          (default "coordinator")
  ledger_dir        where leads.jsonl and handoffs.jsonl go  (default ~/.local/state/bosmang)
  authority_matrix  path to a markdown table replacing the bundled one
  append            paths to markdown files appended after the orders, for local rules

--print writes the rendered orders as plain text instead of hook JSON.
--check reports where the config was read from and every problem with it, and exits 1 if any.
"""

import json
import os
import shlex
import sys
from pathlib import Path
from string import Template

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = Path.home() / ".config" / "bosmang" / "config.json"


KEYS = {"owner", "coordinator", "ledger_dir", "authority_matrix", "append"}


def config_path():
    return Path(os.environ.get("BOSMANG_CONFIG", DEFAULT_CONFIG)).expanduser()


def load_config():
    path = config_path()
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def problems(config):
    found = [f"unknown key {k!r}" for k in sorted(set(config) - KEYS)]
    for key in ("owner", "coordinator"):
        if key in config and not (isinstance(config[key], str) and config[key].strip()):
            found.append(f"{key} must be a non-empty string")
    paths = [("authority_matrix", config["authority_matrix"])] if config.get("authority_matrix") else []
    paths += [("append", p) for p in config.get("append", [])]
    for key, p in paths:
        if not Path(p).expanduser().is_file():
            found.append(f"{key}: no such file {p}")
    ledger = config.get("ledger_dir")
    if ledger and Path(ledger).expanduser().exists() and not Path(ledger).expanduser().is_dir():
        found.append(f"ledger_dir: {ledger} exists and is not a directory")
    return found


def check():
    path = config_path()
    if not path.exists():
        print(f"no config at {path}; using defaults")
        return 0
    try:
        config = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        print(f"{path}: not valid JSON: {e}")
        return 1
    print(f"config: {path}" + (f" -> {path.resolve()}" if path.is_symlink() else ""))
    found = problems(config)
    for p in found:
        print(f"  problem: {p}")
    if not found:
        print("  ok")
    return 1 if found else 0


def read(path):
    return Path(path).expanduser().read_text().strip()


def render(config):
    matrix = config.get("authority_matrix") or PLUGIN_ROOT / "authority-matrix.md"
    ledger = PLUGIN_ROOT / "scripts" / "ledger.py"
    text = Template((PLUGIN_ROOT / "charter.md").read_text()).safe_substitute(
        owner=config.get("owner", "the human"),
        coordinator=config.get("coordinator", "coordinator"),
        matrix=read(matrix),
        ledger=f"python3 {shlex.quote(str(ledger))}",
    )
    parts = [text.strip()] + [read(p) for p in config.get("append", [])]
    return "\n\n".join(parts) + "\n"


def main():
    if "--check" in sys.argv:
        sys.exit(check())
    text = render(load_config())
    if "--print" in sys.argv:
        sys.stdout.write(text)
        return
    json.dump({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text}}, sys.stdout)


if __name__ == "__main__":
    main()
