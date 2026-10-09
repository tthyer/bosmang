#!/usr/bin/env python3
"""Append-only ledger of leads, handoffs, questions and notices, shared by every session in the crew.

Each change is one JSON line appended under an exclusive lock, so sessions writing at the same moment never overwrite each other, and the files double as history. Current state is the fold of all events: the last event for a key wins.

Leads are keyed by scope, not session name, because sessions rename themselves. The
coordinator is recorded by session ID, so /bosmang:resume can bring that same session back.

The ledger directory comes from the same config as charter.py (ledger_dir), overridable
with $BOSMANG_LEDGER_DIR.
"""

import argparse
import fcntl
import json
import os
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_CONFIG = Path.home() / ".config" / "bosmang" / "config.json"
DEFAULT_DIR = Path.home() / ".local" / "state" / "bosmang"


def config():
    path = Path(os.environ.get("BOSMANG_CONFIG", DEFAULT_CONFIG)).expanduser()
    return json.loads(path.read_text()) if path.exists() else {}


def ledger_dir():
    if "BOSMANG_LEDGER_DIR" in os.environ:
        return Path(os.environ["BOSMANG_LEDGER_DIR"]).expanduser()
    configured = config().get("ledger_dir")
    return Path(configured).expanduser() if configured else DEFAULT_DIR


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def exclusive():
    """Hold the ledger's write lock. Every command that changes the ledger runs under it,
    so the state a command checks is still the state when its event lands."""
    directory = ledger_dir()
    directory.mkdir(parents=True, exist_ok=True)
    f = open(directory / ".lock", "a")
    fcntl.flock(f, fcntl.LOCK_EX)
    return f


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
            # /clear ends the conversation, not the terminal's hold on its scope: the
            # session that replaces it takes a "cleared" lead over in session_start_hook.
            event = "cleared" if reason == "clear" else "ended"
            ended.append(append("leads.jsonl", {"ts": now(), "event": event, "scope": lead["scope"], "reason": reason}))
    return ended


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
                # After the lead's own session runs /clear, its replacement in this worktree inherits it.
                mine = source == "clear" and lead["event"] == "cleared" and lead["scope"] in here
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


def new_id(name):
    """A short random ID no item in this file has used. Callers hold the write lock."""
    taken = set(fold(name, "id"))
    item_id = secrets.token_hex(3)
    while item_id in taken:
        item_id = secrets.token_hex(3)
    return item_id


def close_item(name, kind, item_id, note):
    if item_id not in {i["id"] for i in open_items(name, "id")}:
        sys.exit(f"no open {kind} with id {item_id!r}")
    event = {"ts": now(), "event": "close", "id": item_id}
    if note:
        event["note"] = note
    return append(name, event)


def handoff_add(args):
    event = {
        "ts": now(),
        "event": "open",
        "id": new_id("handoffs.jsonl"),
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
    return close_item("handoffs.jsonl", "handoff", args.id, args.note)


def question_add(args):
    """A question only the owner can answer, recorded once so it is asked once and stays in view."""
    event = {"ts": now(), "event": "open", "id": new_id("questions.jsonl"), "scope": args.scope, "text": args.text}
    return append("questions.jsonl", event)


def question_answer(args):
    return close_item("questions.jsonl", "question", args.id, args.answer)


def notice_add(args):
    """A standing notice: injected into every session at start until it is withdrawn."""
    event = {"ts": now(), "event": "open", "id": new_id("notices.jsonl"), "text": args.text, "from": args.from_}
    return append("notices.jsonl", event)


def notice_close(args):
    return close_item("notices.jsonl", "notice", args.id, args.note)


def notices_text():
    """The open notices as injected at session start, or "" when there are none."""
    notices = open_items("notices.jsonl", "id")
    if not notices:
        return ""
    lines = ["## Standing notices", "", "In force for every session until withdrawn. They override nothing $owner tells you directly."]
    lines += [f"- {n['text']} ({n['id']}, from {n['from']}, {n['ts'][:10]})" for n in notices]
    return "\n".join(lines)


def show(args):
    leads = open_items("leads.jsonl", "scope")
    handoffs = sorted(open_items("handoffs.jsonl", "id"), key=lambda h: h.get("due", "9999"))
    questions = open_items("questions.jsonl", "id")
    notices = open_items("notices.jsonl", "id")
    coord = coordinator()
    if args.json:
        return {"coordinator": coord, "leads": leads, "handoffs": handoffs, "questions": questions, "notices": notices}
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
    lines += [f"Waiting on {config().get('owner', 'the human')}:"] + [f"  {q['id']}  {q['scope']}  {q['text']}" for q in questions]
    lines += ["Notices:"] + [f"  {n['id']}  {n['text']}  (from {n['from']})" for n in notices]
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

    question = sub.add_parser("question", help="questions only the owner can answer").add_subparsers(dest="action", required=True)
    qa = question.add_parser("add")
    qa.add_argument("--scope", required=True)
    qa.add_argument("--text", required=True)
    qa.set_defaults(fn=question_add)
    qn = question.add_parser("answer")
    qn.add_argument("id")
    qn.add_argument("--answer", required=True, help="the owner's answer, in brief")
    qn.set_defaults(fn=question_answer)

    notice = sub.add_parser("notice", help="standing notices every session gets at start").add_subparsers(dest="action", required=True)
    na = notice.add_parser("add")
    na.add_argument("--text", required=True)
    na.add_argument("--from", dest="from_", required=True)
    na.set_defaults(fn=notice_add)
    nc = notice.add_parser("close")
    nc.add_argument("id")
    nc.add_argument("--note")
    nc.set_defaults(fn=notice_close)

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
    if args.fn is show:
        result = show(args)
    else:
        with exclusive():
            result = args.fn(args)
    if result is not None:
        print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
