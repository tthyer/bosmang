# Privacy

bosmang collects nothing and sends nothing anywhere. It has no server, no telemetry and no network calls of its own. Everything it writes stays on your machine, in files you can read and delete.

## What it reads

- Its config, at `~/.config/bosmang/config.json` or `$BOSMANG_CONFIG`, and the local rules, procedures and authority matrix that config names.
- The JSON Claude Code passes to its `SessionStart` and `SessionEnd` hooks: the session ID, the working directory, and how the session started or ended. It never reads the conversation.

## What it writes

The ledger, in `ledger_dir` (default `~/.local/state/bosmang`), as three append-only JSONL files:

- `leads.jsonl`: each lead's scope, session name, session ID, and branch and worktree path if given, with timestamps, plus a line each time its session ends, resumes or closes.
- `handoffs.jsonl`: each handoff's text, who it is from and for, its due date and any note, as written by a session or by you.
- `coordinator.jsonl`: the coordinator's session name, session ID and working directory.

The ledger holds no conversation content beyond the handoff text a session chooses to write. `/bosmang:init` writes the config files you install with `charter.py --install`, and backs up anything it replaces beside them.

## What it runs

The hooks run its Python scripts locally. `/bosmang:init` runs `survey.py`, which checks whether tools such as `git`, `gh` and your tracker's CLI are installed and signed in by reading only their exit codes. If `gh` is signed in, it asks GitHub for your login and the repos you merged PRs into in the last 90 days, using your own `gh` credentials. That result goes to the session and is not stored. Commands in your own procedures run only when a skill carries them out, under Claude Code's permissions.

## Removing it

Uninstall the plugin, then delete `~/.config/bosmang` and your `ledger_dir`.
