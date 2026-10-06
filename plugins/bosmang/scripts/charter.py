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
"""

import json
import os
import shlex
import sys
from pathlib import Path
from string import Template

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = Path.home() / ".config" / "bosmang" / "config.json"


def load_config():
    path = Path(os.environ.get("BOSMANG_CONFIG", DEFAULT_CONFIG)).expanduser()
    if not path.exists():
        return {}
    return json.loads(path.read_text())


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
    text = render(load_config())
    if "--print" in sys.argv:
        sys.stdout.write(text)
        return
    json.dump({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text}}, sys.stdout)


if __name__ == "__main__":
    main()
