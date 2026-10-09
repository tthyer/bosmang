# Changelog

Each version is tagged `vX.Y.Z`. Claude Code installs a new copy of the plugin only when `version` in `plugin.json` changes, so every release bumps it.

## 0.6.1 (2026-10-08)

- The launchers are written by every run of `ledger.py` or `charter.py`, not only at a fresh session start. `/reload-plugins` fires no hook, so a crew that only reloaded had none. A run from an older copy never points them back at itself.
- Close-on-merge asks first. 0.6.0's board told a lead to close as soon as its PR merged, but only you close a scope. Now a lead asks you once, recording the question in the ledger, when its PR merges; the board asks across all merged leads at once; and only a scope you say is closed gets `/bosmang:close`.

## 0.6.0 (2026-10-08)

From the coordinator's and a lead's feedback after two days of real use.

- **Your word wins.** The orders say your direct instruction in a session overrides any standing rule or notice; the session follows it and reports the departure as `[STATE]`.
- **Questions waiting on you.** `ledger.py question add` records a question only you can answer, so a lead asks it once. `/bosmang:board` lists open questions first, by lead, until `question answer` closes them.
- **Standing notices.** `ledger.py notice add` records a rule for the whole crew. Every session gets open notices at start, as a third injected part, so sessions started later no longer miss a broadcast. The coordinator adds a notice and messages the live sessions.
- **Launchers at a fixed path.** The orders now name `~/.local/share/bosmang/bin/ledger` and `…/charter`, which each session start points at the installed plugin. Sessions started before an auto-update used to keep calling the old version's scripts.
- **Close when merged.** `/bosmang:board` checks each lead's branch for a merged PR. (0.6.1 makes this ask you first.)

## 0.5.6 (2026-10-07)

Fixes from a code review.

- `charter.py --draft <dir>` previews a drafted config with its own files, exactly as `--install` would install it. `/bosmang:init` uses it, so the preview you approve is what gets installed.
- `--install` writes each file to the path `config.json` names for it, and `config.json` to the config in use, including a custom `$BOSMANG_CONFIG` name. It refuses a file the config doesn't name. Validation, preview and install share one mapping.
- Every ledger change runs under one exclusive lock, so a check and the event it allows can't interleave with another write (a `close` could be undone by a racing `resumed`).
- Handoff IDs are random and checked against existing ones. Two identical handoffs added in the same second used to share an ID.
- After `/clear`, a lead passes to the new session only when the lead's own session cleared.
- `/bosmang:resume` and the coordinator also treat a lead as orphaned when its session isn't in `claude agents --json`, which catches crashes that skip the exit hook.

## 0.5.5 (2026-10-07)

- A lead with a recorded session ID is reclaimed only by that session, from any directory. Previously any session starting in the lead's worktree took an orphaned lead, and the lead's own session missed it when resumed from elsewhere. Another session now takes a scope over with `/bosmang:lead`.
- A teammate whose project has lost its lead reports it to the coordinator as `[STATE]`, and does nothing beyond its own step.

## 0.5.4 (2026-10-07)

- `ledger.py handoff update <id>` changes an open handoff's item, owner, due date or note, and keeps its ID.
- The standing orders say the config, local rules, procedures and authority matrix belong to the user, and give the `charter.py --install` command for proposing a change.
- `/bosmang:init` offers a closing step that commits the ledger when it lives in a git repo. The README documents where the ledger lives and how to back it up.
- Files for the Claude plugin directory: a README, LICENSE and PRIVACY.md in the plugin folder, and `license`, `homepage`, `repository`, `keywords` and `privacyPolicyUrl` in `plugin.json`.
- README: a Status section, and a Prior art section that credits Gas Town, claude-team and Claude Code Projects in full.

## 0.5.3 (2026-10-06)

- `/bosmang:init` sets up a fresh machine: it reports missing tools, whether git has an identity, and offers the install and sign-in commands for you to run.
- It never asks for your forge handle (procedures use `@me`), and offers the repos you recently merged PRs into for `/bosmang:board`.

## 0.5.2 (2026-10-06)

- `survey.py` gathers what `/bosmang:init` needs in one quick call. The search for conflicting rules runs in the background.

## 0.5.1 (2026-10-06)

- `/bosmang:init` and `/bosmang:resume` ask with question forms, one topic per form.

## 0.5.0 (2026-10-06)

- `charter.py --install <dir>` validates a drafted config and moves it into place, with backups and writing through symlinks. `/bosmang:init` drafts; you install with one command.
- `/bosmang:init` lists the permission rules your no-ask steps need, for the source of a generated settings file where there is one.
- `/bosmang:board` shows what's in flight, and refreshes your own dashboard.

## 0.4.1 (2026-10-06)

- `/bosmang:init` recommends `nagata` as the coordinator's name.

## 0.4.0 (2026-10-06)

- `/bosmang:init` records the running sessions' handoffs and scopes, stops them after one confirmation, and starts the coordinator in the background.
- `/bosmang:resume` brings back the recorded coordinator session, then offers to resume orphaned leads. The ledger records the coordinator's session.

## 0.3.0 (2026-10-06)

- Session hooks mark a lead orphaned when its own session ends, and hand it back on resume. Ending a session never closes a scope.
- The coordinator owns meta-coordination: ownership, boundaries, order and disputes between scopes.
- The orders are injected in parts, each under Claude Code's 10,000-character hook limit.
- "Decide, don't do": how-to detail moves to a procedures file that skills read on demand. The default orders went from about 8.9K to 4.9K characters.

## 0.2.0 (2026-10-06)

- `/bosmang:init` opens by asking how you'd like to be addressed, and records pronouns only when given.

## 0.1.0 (2026-10-06)

- First version: a `SessionStart` hook that injects the standing orders (roles, authority matrix, typed messages), an append-only ledger of leads and handoffs, the coordinator and project-lead agents, and `/bosmang:lead`, `/bosmang:init` and `/bosmang:close`.
