#!/usr/bin/env python3
"""Append-only ledger of project leads and handoffs, shared by every session in the crew.

Each change is one JSON line appended under an exclusive lock, so sessions writing at the same moment never overwrite each other, and the files double as history. Current state is the fold of all events: the last event for a key wins.

Leads are keyed by scope, not session name, because sessions rename themselves. The
coordinator is recorded by session ID, so /bosmang:resume can bring that same session back.

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


def resolve(path):
    return str(Path(path).expanduser().resolve())


def lead_open(args):
    event = {"ts": now(), "event": "open", "scope": args.scope, "session": args.session}
    if args.branch:
        event["branch"] = args.branch
    if args.worktree:
        event["worktree"] = resolve(args.worktree)
    # Claude Code exports the running session's ID to its tools. Recording it lets the
    # session hooks tell the lead's own session from a visitor in the same worktree.
    session_id = args.session_id or os.environ.get("CLAUDE_CODE_SESSION_ID")
    if session_id:
        event["session_id"] = session_id
    return append("leads.jsonl", event)


def leads_in(cwd):
    """Open leads whose registered worktree is cwd or contains it."""
    cwd = Path(resolve(cwd))
    return [
        lead
        for lead in open_items("leads.jsonl", "scope")
        if lead.get("worktree") and (cwd == Path(lead["worktree"]) or Path(lead["worktree"]) in cwd.parents)
    ]


def lead_ended(session_id, cwd, reason):
    """Record that a lead's own session ended. Closes nothing.

    A lead with a recorded session_id is matched by it alone, so another session ending
    in the same worktree (a headless `claude -p` run reports reason "other", not the
    documented prompt_input_exit) leaves it alone. A lead without one falls back to its
    worktree."""
    ended = []
    for lead in open_items("leads.jsonl", "scope"):
        mine = lead.get("session_id") == session_id if lead.get("session_id") else lead in leads_in(cwd)
        if mine and lead["event"] != "ended":
            ended.append(append("leads.jsonl", {"ts": now(), "event": "ended", "scope": lead["scope"], "reason": reason}))
    return ended


# /clear ends the conversation, not the terminal's hold on its scope; the session that
# replaces it takes the lead over in session_start_hook.
IGNORED_END_REASONS = {"clear"}


def session_start_hook(args):
    """SessionStart hook entry: a lead's own session coming back (a --resume keeps its ID)
    takes its orphaned lead back, from any directory. Prints nothing; never fails the start.

    Another session starting in the worktree takes nothing: it may be a visitor, and if
    it took the lead, its own exit would orphan the lead while the real lead still ran.
    A new session takes a scope over with /bosmang:lead."""
    try:
        payload = json.load(sys.stdin)
        session_id, source = payload.get("session_id"), payload.get("source")
        here = {lead["scope"] for lead in leads_in(payload["cwd"])}
        for lead in open_items("leads.jsonl", "scope"):
            if lead["event"] == "ended":
                # A lead recorded without a session ID can only be matched by its worktree.
                mine = lead.get("session_id") == session_id if lead.get("session_id") else lead["scope"] in here
            else:
                # After /clear, the new session in this worktree inherits a live lead from the old one.
                mine = source == "clear" and lead["scope"] in here and lead.get("session_id") != session_id
            if mine:
                event = {"ts": now(), "event": "resumed", "scope": lead["scope"]}
                if session_id:
                    event["session_id"] = session_id
                append("leads.jsonl", event)
    except Exception:  # noqa: BLE001 -- a hook must never break startup
        pass
    return None


def session_end_hook(args):
    """SessionEnd hook entry: reads the hook's JSON on stdin. Never fails the session's exit."""
    try:
        payload = json.load(sys.stdin)
        if payload.get("reason") not in IGNORED_END_REASONS:
            lead_ended(payload.get("session_id"), payload.get("cwd", "."), payload.get("reason", "other"))
    except Exception:  # noqa: BLE001 -- a hook must never break exit
        pass
    return None


def coordinator_set(args):
    session_id = args.session_id or os.environ.get("CLAUDE_CODE_SESSION_ID")
    if not session_id:
        sys.exit("no --session-id, and $CLAUDE_CODE_SESSION_ID is not set")
    event = {"ts": now(), "role": "coordinator", "name": args.name, "session_id": session_id, "cwd": resolve(args.cwd)}
    return append("coordinator.jsonl", event)


def coordinator():
    return fold("coordinator.jsonl", "role").get("coordinator")


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


def handoff_update(args):
    """Change an open handoff in place, so anyone holding its ID still finds it."""
    if args.id not in {h["id"] for h in open_items("handoffs.jsonl", "id")}:
        sys.exit(f"no open handoff with id {args.id!r}")
    changes = {k: v for k, v in (("item", args.item), ("owner", args.owner), ("due", args.due), ("note", args.note)) if v}
    if not changes:
        sys.exit("nothing to update: give --item, --owner, --due or --note")
    return append("handoffs.jsonl", {"ts": now(), "event": "update", "id": args.id, **changes})


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
    coord = coordinator()
    if args.json:
        return {"coordinator": coord, "leads": leads, "handoffs": handoffs}
    lines = [f"Coordinator: {coord['name']}  session {coord['session_id'][:8]}  in {coord['cwd']}" if coord else "Coordinator: none recorded"]
    lines.append("Leads:")
    for l in leads:
        line = f"  {l['scope']}  {l['session']}"
        if l["event"] != "ended":
            line += f"  since {l['ts'][:10]}"
        else:
            line += f"  ORPHANED: session ended {l['ts'][:16].replace('T', ' ')} ({l['reason']}), not closed"
        lines.append(line)
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
    o.add_argument("--session-id", help="defaults to $CLAUDE_CODE_SESSION_ID")
    o.set_defaults(fn=lead_open)
    c = lead.add_parser("close")
    c.add_argument("--scope", required=True)
    c.set_defaults(fn=lead_close)

    coord = sub.add_parser("coordinator").add_subparsers(dest="action", required=True)
    cs = coord.add_parser("set", help="record the coordinator's session, so /bosmang:resume can bring it back")
    cs.add_argument("--name", required=True)
    cs.add_argument("--session-id", help="defaults to $CLAUDE_CODE_SESSION_ID")
    cs.add_argument("--cwd", default=".", help="the directory it runs in; --resume must run from there")
    cs.set_defaults(fn=coordinator_set)

    handoff = sub.add_parser("handoff").add_subparsers(dest="action", required=True)
    a = handoff.add_parser("add")
    a.add_argument("--item", required=True)
    a.add_argument("--from", dest="from_", required=True)
    a.add_argument("--owner")
    a.add_argument("--due", help="YYYY-MM-DD")
    a.set_defaults(fn=handoff_add)
    hu = handoff.add_parser("update", help="change an open handoff; its ID stays the same")
    hu.add_argument("id")
    hu.add_argument("--item")
    hu.add_argument("--owner")
    hu.add_argument("--due", help="YYYY-MM-DD")
    hu.add_argument("--note", help="what changed and why")
    hu.set_defaults(fn=handoff_update)
    hc = handoff.add_parser("close")
    hc.add_argument("id")
    hc.add_argument("--note")
    hc.set_defaults(fn=handoff_close)

    start = sub.add_parser("session-start-hook", help="SessionStart hook entry; reads hook JSON on stdin")
    start.set_defaults(fn=session_start_hook)
    end = sub.add_parser("session-end-hook", help="SessionEnd hook entry; reads hook JSON on stdin")
    end.set_defaults(fn=session_end_hook)

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
