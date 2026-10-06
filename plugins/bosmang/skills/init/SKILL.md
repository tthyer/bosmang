---
name: init
description: Set up bosmang for this user. Writes ~/.config/bosmang/config.json (owner, coordinator name, ledger location, an editable copy of the authority matrix), validates it, retires any older coordination rules it would conflict with, and says how to start the coordinator. Use when the user says "set up bosmang", "bosmang init", "/bosmang:init", "configure bosmang", or changes who the coordinator is. Re-runnable, and it shows the current config first.
---

# init

Run every script below with `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/<script>"`. If that variable is empty in your shell, the ledger command in the standing orders gives you the absolute path to the same `scripts/` directory.

## 1. Read what exists

Run `charter.py --check`. If it finds a config, show it to the user and ask what they want to change. Don't start over. If the config is a symlink, the user keeps it somewhere deliberate (often a dotfiles repo): write to the target, never replace the link.

## 2. Ask, one question at a time

1. **Owner:** the name the crew uses for the human. Offer the git `user.name`, or "the human".
2. **Coordinator name:** a session name to use with `-n`. It must not match a running session that isn't the coordinator, so check `ListAgents`.
3. **Ledger location:** default `~/.local/state/bosmang`. Suggest a directory in a git repo if the user wants history and backup, since the ledger is append-only JSONL and diffs cleanly.
4. **Authority matrix:** keep the bundled one, or fork it to `~/.config/bosmang/authority-matrix.md` for editing. Recommend forking, since the rows are where the user's own rules belong. If they fork it, copy the bundled `authority-matrix.md` there and walk through the rows marked "Ask" with them. Change only what they say to change.
5. **Local rules:** an optional markdown file appended after the orders, for tracker conventions, infrastructure rules and naming. Don't create one unless they have something to put in it.

## 3. Write and validate

Write `config.json` with only the keys the user chose. The defaults cover the rest. Then:

- Run `charter.py --check`. It must report `ok`. If it doesn't, fix the problem and run it again.
- Run `charter.py --print` and show the user the roles section and the authority table as their sessions will see them.

## 4. Retire older rules

Earlier coordination rules will contradict the standing orders. Search the user's global `CLAUDE.md`, any `CLAUDE.md` or `CLAUDE.local.md` in the current repo, and the memory directory for this project. Look for: coordinator, a session name used as a coordinator, "report to", "hand off", `SendMessage` conventions.

List what you find, with file and line, and propose for each one whether to delete it, move it into the local-rules file, or leave it. Change nothing until the user says. Where open handoffs live only in a running session's context, have that session record them with `ledger.py handoff add` before anything is restarted.

## 5. Tell them how to start

- **Coordinator:** a fresh session, `claude --agent bosmang:coordinator -n <coordinator name>`. `--agent` applies only when a session is created; resuming an existing session with it does not change its agent.
- **Leads:** `/bosmang:lead <SCOPE>` in any session.
- **Already running sessions:** they pick up the orders when they restart or run `/clear`.

Finish by running `ledger.py list`, so the user sees the ledger's starting state.
