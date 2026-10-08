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
--draft DIR prints the orders a drafted config would give, with the draft's own files.
--procedures prints the procedures files, for skills that need them.
--check reports where the config was read from and every problem with it, and exits 1 if any.
--install DIR moves a drafted config into place: config.json to the config in use, and every
other file to the path config.json gives for a file of that name. /bosmang:init drafts every file in DIR and
the user runs this one command, so changing the standing orders is the user's own single step
rather than a string of approvals. Nothing is installed unless the draft validates; a file
that is a symlink is written through, and anything replaced is backed up first.
"""

import json
import os
import shlex
import shutil
import sys
from datetime import datetime
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


def configured_paths(config):
    paths = [config["authority_matrix"]] if config.get("authority_matrix") else []
    return paths + list(config.get("append", [])) + list(config.get("procedures", []))


def destinations(config, draft):
    """Where each drafted file installs, and any problem with that. config.json goes to the
    config in use; every other file goes to the configured path with its name. Validation,
    preview and install all use this one mapping, so what is checked is what is installed."""
    by_name = {}
    for p in configured_paths(config):
        by_name.setdefault(Path(p).name, set()).add(Path(p).expanduser())
    mapping, found = {}, []
    for source in sorted(f for f in draft.iterdir() if f.is_file()):
        if source.name == "config.json":
            mapping[source] = config_path()
        elif len(by_name.get(source.name, ())) == 1:
            mapping[source] = next(iter(by_name[source.name]))
        elif source.name in by_name:
            found.append(f"{source.name}: config.json names more than one file called that; rename one")
        else:
            found.append(f"{source.name}: config.json names no file called that, so it would not be installed")
    return mapping, found


def drafted(config, draft):
    """The config with every path that names a drafted file pointed at the draft instead,
    so it can be validated and previewed before anything is installed."""
    names = {f.name for f in draft.iterdir() if f.is_file()}

    def swap(p):
        return str(draft / Path(p).name) if Path(p).name in names else p

    config = dict(config)
    if config.get("authority_matrix"):
        config["authority_matrix"] = swap(config["authority_matrix"])
    for key in ("append", "procedures"):
        if key in config:
            config[key] = [swap(p) for p in config[key]]
    return config


def load_draft(draft):
    draft = Path(draft).expanduser().resolve()
    try:
        return draft, json.loads((draft / "config.json").read_text())
    except (OSError, json.JSONDecodeError) as e:
        print(f"{draft / 'config.json'}: {e}")
        return draft, None


def install(draft):
    draft, config = load_draft(draft)
    if config is None:
        return 1
    mapping, found = destinations(config, draft)
    found += problems(drafted(config, draft))
    if found:
        print("not installed; the draft has problems:")
        for p in found:
            print(f"  problem: {p}")
        return 1
    backup = config_path().parent / f"backup-{datetime.now():%Y%m%d-%H%M%S}"
    for source, dest in mapping.items():
        target = dest.resolve() if dest.is_symlink() else dest
        if target.exists() and target.read_bytes() == source.read_bytes():
            print(f"  unchanged  {dest}")
            continue
        if target.exists():
            backup.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, backup / source.name)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        print(f"  {'replaced' if (backup / source.name).exists() else 'new':<9}  {dest}" + (f" -> {target}" if target != dest else ""))
    if backup.exists():
        print(f"  backup of what was replaced: {backup}")
    return check()


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
        charter=f"python3 {shlex.quote(str(Path(__file__).resolve()))}",
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
    if "--install" in sys.argv:
        sys.exit(install(sys.argv[sys.argv.index("--install") + 1]))
    if "--check" in sys.argv:
        sys.exit(check())
    if "--draft" in sys.argv:
        # Preview a draft exactly as --install would validate and install it.
        draft, config = load_draft(sys.argv[sys.argv.index("--draft") + 1])
        if config is None:
            sys.exit(1)
        config = drafted(config, draft)
        found = destinations(config, draft)[1] + problems(config)
        if found:
            sys.exit("the draft has problems:\n" + "\n".join(f"  problem: {p}" for p in found))
        sys.stdout.write(render(config).rstrip() + "\n")
        return
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
