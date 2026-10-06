#!/usr/bin/env python3
"""SessionStart hook: render the standing orders and hand them to Claude Code as context.

Runs on every session start, including after /clear and compaction, which is the point: the orders are re-read rather than remembered.

Config is JSON at $BOSMANG_CONFIG, else ~/.config/bosmang/config.json. Every key is optional:

  owner             who the crew works for                  (default "the human")
  coordinator       the coordinator session's name          (default "coordinator")
  ledger_dir        where leads.jsonl and handoffs.jsonl go  (default ~/.local/state/bosmang)
  authority_matrix  path to a markdown table replacing the bundled one
  append            paths to markdown injected after the orders: local rules that change
                    how a session decides. Keep them short; they cost context in every session.
  procedures        paths to markdown NOT injected: exact commands, templates and routines
                    (tracker, version control, closing steps). Skills read them with
                    --procedures when they run.

Claude Code shows a hook's additionalContext only up to 10,000 characters; anything
longer reaches the session as a 2KB preview and a file path, which a session can miss
entirely. So the orders are injected in parts, each by its own hook call (--part orders,
--part local), and a part that is still too long is replaced by a pointer to read it in
full rather than silently previewed.

--print writes the rendered orders as plain text instead of hook JSON (one --part, or all).
--procedures prints the procedures files, for skills that need them.
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


KEYS = {"owner", "coordinator", "ledger_dir", "authority_matrix", "append", "procedures"}


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
    try:
        for part, text in render_parts(config).items():
            if len(text) >= HOOK_LIMIT:
                found.append(f"the {part} part is {len(text):,} characters, over the {HOOK_LIMIT:,} hook limit; shorten it")
    except OSError:
        pass  # a missing file is reported below
    paths = [("authority_matrix", config["authority_matrix"])] if config.get("authority_matrix") else []
    paths += [("append", p) for p in config.get("append", [])]
    paths += [("procedures", p) for p in config.get("procedures", [])]
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
    if not [p for p in found if "no such file" in p]:
        parts = render_parts(config)
        for part, text in parts.items():
            print(f"  {part}: {len(text):,} of {HOOK_LIMIT:,} characters")
        injected = sum(len(t) for t in parts.values())
        if injected > INJECTED_BUDGET:
            print(f"  note: {injected:,} characters injected into every session, over the {INJECTED_BUDGET:,} budget."
                  " Move commands, templates and routines from the local rules into procedures.")
    for p in found:
        print(f"  problem: {p}")
    if not found:
        print("  ok")
    return 1 if found else 0


def read(path):
    return Path(path).expanduser().read_text().strip()


HOOK_LIMIT = 10_000  # measured on 2.1.292: 9,900 characters shown whole, 10,100 previewed
PARTS = ("orders", "local")
# Injected text is paid for in every session's context, so it carries only what changes
# how a session decides. Past this, --check suggests moving procedure into procedures.
INJECTED_BUDGET = 7_000


def render(config):
    return "\n\n".join(text for text in render_parts(config).values() if text) + "\n"


def render_parts(config):
    matrix = config.get("authority_matrix") or PLUGIN_ROOT / "authority-matrix.md"
    ledger = PLUGIN_ROOT / "scripts" / "ledger.py"
    text = Template((PLUGIN_ROOT / "charter.md").read_text()).safe_substitute(
        owner=config.get("owner", "the human"),
        coordinator=config.get("coordinator", "coordinator"),
        matrix=read(matrix),
        ledger=f"python3 {shlex.quote(str(ledger))}",
    )
    return {"orders": text.strip(), "local": "\n\n".join(read(p) for p in config.get("append", []))}


def hook_text(part, text):
    if len(text) < HOOK_LIMIT:
        return text
    command = f"python3 {shlex.quote(str(Path(__file__).resolve()))} --print --part {part}"
    return (
        f"Part of your bosmang standing orders ({part}, {len(text):,} characters) is over Claude Code's "
        f"{HOOK_LIMIT:,}-character limit for hook context, so it is not shown here. Read it in full now, "
        f"before doing anything else: `{command}`"
    )


def main():
    if "--check" in sys.argv:
        sys.exit(check())
    if "--procedures" in sys.argv:
        config = load_config()
        sys.stdout.write("\n\n".join(read(p) for p in config.get("procedures", [])) + "\n")
        return
    part = sys.argv[sys.argv.index("--part") + 1] if "--part" in sys.argv else None
    if part is not None and part not in PARTS:
        sys.exit(f"--part must be one of {', '.join(PARTS)}")
    parts = render_parts(load_config())
    if "--print" in sys.argv:
        sys.stdout.write((parts[part] if part else render(load_config())).rstrip() + "\n")
        return
    text = hook_text(part or "orders", parts[part or "orders"])
    if text:
        json.dump({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text}}, sys.stdout)


if __name__ == "__main__":
    main()
