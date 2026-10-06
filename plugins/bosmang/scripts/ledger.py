#!/usr/bin/env python3
"""Append-only ledger of project leads and handoffs, shared by every session in the crew.

Each change is one JSON line appended under an exclusive lock, so sessions writing at the
same moment never overwrite each other, and the files double as history. Current state is
the fold of all events: the last event for a key wins.

Leads are keyed by scope, not session name, because sessions rename themselves.

The ledger directory comes from the same config as charter.py (ledger_dir), overridable
with $BOSMANG_LEDGER_DIR.
"""

import argparse
import fcntl
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_CONFIG = Path.home() / ".config" / "bosmang" / "config.json"
DEFAULT_DIR = Path.home() / ".local" / "state" / "bosmang"


def ledger_dir():
    if "BOSMANG_LEDGER_DIR" in os.environ:
        return Path(os.environ["BOSMANG_LEDGER_DIR"]).expanduser()
    config = Path(os.environ.get("BOSMANG_CONFIG", DEFAULT_CONFIG)).expanduser()
    if config.exists():
        configured = json.loads(config.read_text()).get("ledger_dir")
        if configured:
            return Path(configured).expanduser()
    return DEFAULT_DIR


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def append(name, event):
    directory = ledger_dir()
    directory.mkdir(parents=True, exist_ok=True)
    with open(directory / name, "a", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.write(json.dumps(event, sort_keys=True) + "\n")
    return event


def events(name):
    path = ledger_dir() / name
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_SH)
        return [json.loads(line) for line in f if line.strip()]


def fold(name, key):
    state = {}
    for event in events(name):
        state.setdefault(event[key], {}).update(event)
    return state


def open_items(name, key):
    return [item for item in fold(name, key).values() if item["event"] != "close"]


def lead_open(args):
    event = {"ts": now(), "event": "open", "scope": args.scope, "session": args.session}
    event.update({k: v for k, v in (("branch", args.branch), ("worktree", args.worktree)) if v})
    return append("leads.jsonl", event)


def lead_close(args):
    if args.scope not in {lead["scope"] for lead in open_items("leads.jsonl", "scope")}:
        sys.exit(f"no open lead for scope {args.scope!r}")
    return append("leads.jsonl", {"ts": now(), "event": "close", "scope": args.scope})


def handoff_add(args):
    ts = now()
    event = {
        "ts": ts,
        "event": "open",
        "id": hashlib.sha1(f"{ts}{args.item}".encode()).hexdigest()[:6],
        "item": args.item,
        "from": args.from_,
    }
    event.update({k: v for k, v in (("owner", args.owner), ("due", args.due)) if v})
    return append("handoffs.jsonl", event)


def handoff_close(args):
    if args.id not in {h["id"] for h in open_items("handoffs.jsonl", "id")}:
        sys.exit(f"no open handoff with id {args.id!r}")
    event = {"ts": now(), "event": "close", "id": args.id}
    if args.note:
        event["note"] = args.note
    return append("handoffs.jsonl", event)


def show(args):
    leads = open_items("leads.jsonl", "scope")
    handoffs = sorted(open_items("handoffs.jsonl", "id"), key=lambda h: h.get("due", "9999"))
    if args.json:
        return {"leads": leads, "handoffs": handoffs}
    lines = ["Leads:"] + [f"  {l['scope']}  {l['session']}  since {l['ts'][:10]}" for l in leads]
    lines += ["Handoffs:"] + [
        f"  {h['id']}  {h.get('due', '')}  {h['item']}  (from {h['from']}"
        + (f", for {h['owner']})" if "owner" in h else ")")
        for h in handoffs
    ]
    print("\n".join(lines))
    return None


def parser():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    lead = sub.add_parser("lead").add_subparsers(dest="action", required=True)
    o = lead.add_parser("open")
    o.add_argument("--scope", required=True)
    o.add_argument("--session", required=True)
    o.add_argument("--branch")
    o.add_argument("--worktree")
    o.set_defaults(fn=lead_open)
    c = lead.add_parser("close")
    c.add_argument("--scope", required=True)
    c.set_defaults(fn=lead_close)

    handoff = sub.add_parser("handoff").add_subparsers(dest="action", required=True)
    a = handoff.add_parser("add")
    a.add_argument("--item", required=True)
    a.add_argument("--from", dest="from_", required=True)
    a.add_argument("--owner")
    a.add_argument("--due", help="YYYY-MM-DD")
    a.set_defaults(fn=handoff_add)
    hc = handoff.add_parser("close")
    hc.add_argument("id")
    hc.add_argument("--note")
    hc.set_defaults(fn=handoff_close)

    ls = sub.add_parser("list")
    ls.add_argument("--json", action="store_true")
    ls.set_defaults(fn=show)
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    result = args.fn(args)
    if result is not None:
        print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
