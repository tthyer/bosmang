---
name: init
description: Set up bosmang for this user. Asks how they track work and versions, who they are and what to call the coordinator. Writes ~/.config/bosmang/config.json and a local-rules file (tracker, version control, closing steps), forks the authority matrix, validates everything, and finds older rules and skills that would conflict. Use when the user says "set up bosmang", "bosmang init", "/bosmang:init", "configure bosmang", or changes their tracker, tools or coordinator. Re-runnable, and it starts from the current config.
---

# init

Run every script below with `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/<script>"`. If that variable is empty in your shell, the ledger command in the standing orders gives you the absolute path to the same `scripts/` directory.

Ask **one question at a time**, and offer a recommended answer where there is one. Before asking about a tool, check what's already installed and signed in, so the question can say what you found.

## 1. Read what exists

Run `charter.py --check`. If a config exists, show it and the local-rules file it points to, and ask what the user wants to change; don't start over. If a file is a symlink, the user keeps it somewhere deliberate (often a dotfiles repo): write to the target, never replace the link.

## 2. The basics

1. **"How would you like to be addressed?"** Ask this first, and in these words. The answer becomes `owner`, the name every session uses for the human in the standing orders and in reports. Don't propose a name taken from git or the OS account; a username isn't how someone wants to be addressed. Then ask whether sessions should refer to them with particular pronouns. If they give some, write one line into the local rules, such as "Refer to Ada as she/her." If not, sessions use the name, or "they".
2. **Coordinator name:** a session name to use with `-n`. It must not match a running session that isn't the coordinator, so check `ListAgents`.
3. **Ledger location:** default `~/.local/state/bosmang`. Suggest a directory in a git repo if the user wants history and backup, since the ledger is append-only JSONL and diffs cleanly.

## 3. How they work

Each answer becomes a section of the local-rules file (default `~/.config/bosmang/local-rules.md`, listed under `append` in the config). Write the sections as instructions to a session, with the exact commands.

**Tracker: "How do you track work?"**
- **They use a tracker** (Jira, Linear, GitHub Issues, or something else). Ask which CLI sessions should use, then check it's installed and signed in with a read-only command, such as `acli jira auth status`, `gh auth status` or `linear --version`. Record:
  - how to read an item's status;
  - how to transition one, and which transitions a session may make without asking;
  - the key format;
  - whether new items need a project or epic the user names (if so, sessions always ask);
  - how branch names and PR titles carry the key.
- **They'd like bosmang to track it.** Scopes are short slugs (`auth-refactor`), the ledger's leads are the open scopes, and its handoffs are the to-do list. Say so in the section, so sessions never invent a ticket key.

**Version control: "How do you keep track of code versions?"**
- Recommend **git**. If they host on GitHub, recommend **`gh`** for PRs, checks and reviews; check `gh auth status`. For another host, ask for its CLI (for example `glab`).
- Ask how they make a working copy for parallel work: `git worktree`, a wrapper such as worktrunk (`wt`), or separate clones. Record the exact creation command; one session per worktree avoids sessions editing the same checkout.
- Ask whether PRs open as drafts, and how branches are named.

**Closing steps: "When a piece of work closes, what else should happen?"** `/bosmang:close` already checks live state, sums up, records handoffs and reports `[DONE]`. These steps come after it. Offer the usual ones:
- moving the ticket to Done;
- removing the worktree;
- writing a log or journal entry, with its path and format;
- notifying someone.

For each step the user wants, ask whether a session may do it **without asking**, and set the matching authority-matrix row to agree. A closing step and the matrix must never contradict each other.

## 4. The authority matrix

Offer to fork the bundled `authority-matrix.md` to `~/.config/bosmang/authority-matrix.md`; recommend it, since the rows are where the user's own rules belong. Fold in what step 3 settled, such as ticket transitions and worktree removal. Then walk through the remaining "Ask" rows. Change only what the user says to change.

## 5. Write and validate

Write `config.json` with only the keys chosen, since the defaults cover the rest. Then:

- Run `charter.py --check`. It must report `ok`; fix it and run it again until it does.
- Run `charter.py --print` and show the user the roles section, the authority table and their local rules, as their sessions will see them.

## 6. Retire what conflicts

Older rules and skills that contradict the orders will win, because they're more specific and are loaded right when the work happens. Search all of these:

- **Instructions:** the global `CLAUDE.md` and every file it imports, plus any `CLAUDE.md` or `CLAUDE.local.md` in the current repo and its `.claude/rules/`.
- **Memory:** the memory directory for this project.
- **Skills and agents:** `~/.claude/skills/`, `~/.claude/agents/`, the repo's `.claude/skills/` and `.claude/agents/`, and the skills of every other installed plugin (under `~/.claude/plugins/marketplaces/*/plugins/*/skills/`).

Look for anything that:
- names a coordinator, or tells sessions to report or hand off somewhere other than the ledger;
- closes, wraps up or hands off a thread;
- **acts where the matrix says "Ask"**, or asks where the matrix says "Yes". Check for pushes, merges, ticket transitions, worktree removal, production writes and posting to people.

List each finding with its file and line, and propose one of: delete it, move it into the local rules (a skill's closing ritual usually becomes closing steps), or leave it and change the matrix to match. Change nothing until the user says. If open handoffs live only in a running session's context, have that session record them with `ledger.py handoff add` before anything is restarted or retired.

## 7. Tell them how to start

- **Coordinator:** a fresh session, `claude --agent bosmang:coordinator -n <coordinator name>`. `--agent` applies only when a session is created; resuming an existing session with it does not change its agent.
- **Leads:** `/bosmang:lead <SCOPE>`. **Closing:** `/bosmang:close`.
- **Already running sessions:** they pick up the orders when they restart or run `/clear`.

Finish by running `ledger.py list`, so the user sees the ledger's starting state.
