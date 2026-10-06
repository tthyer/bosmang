---
name: init
description: Set up bosmang for this user. Asks how they track work and versions, who they are and what to call the coordinator. Writes ~/.config/bosmang/config.json, short local rules, and a procedures file (tracker, version control, closing steps), forks the authority matrix, validates everything, finds older rules and skills that would conflict, then closes down the running sessions and starts the coordinator. Use when the user says "set up bosmang", "bosmang init", "/bosmang:init", "configure bosmang", or changes their tracker, tools or coordinator. Re-runnable, and it starts from the current config.
---

# init

Run every script below with `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/<script>"`. If that variable is empty in your shell, the ledger command in the standing orders gives you the absolute path to the same `scripts/` directory.

Ask **one question at a time**, and offer a recommended answer where there is one. Before asking about a tool, check what's already installed and signed in, so the question can say what you found.

## 1. Read what exists

Run `charter.py --check`. If a config exists, show it and the local-rules file it points to, and ask what the user wants to change; don't start over. If a file is a symlink, the user keeps it somewhere deliberate (often a dotfiles repo): write to the target, never replace the link.

## 2. The basics

1. **"How would you like to be addressed?"** Ask this first, and in these words. The answer becomes `owner`, the name every session uses for the human in the standing orders and in reports. Don't propose a name taken from git or the OS account; a username isn't how someone wants to be addressed. Then ask whether sessions should refer to them with particular pronouns. If they give some, write one line into the local rules, such as "Refer to Ada as she/her." If not, sessions use the name, or "they".
2. **Coordinator name:** a session name to use with `-n`. It must not match a running session that isn't the coordinator, so check `ListAgents`. Then ask which directory it should run in (recommend the current one). Its project memory belongs to that directory, so pick one the user won't move.
3. **Ledger location:** default `~/.local/state/bosmang`. Suggest a directory in a git repo if the user wants history and backup, since the ledger is append-only JSONL and diffs cleanly.

## 3. How they work

Each answer is split between two files, and getting the split right is what keeps every session's context small:

- **Local rules** (`~/.config/bosmang/local-rules.md`, under `append`) are injected into every session. They hold only what changes how a session *decides*: which tracker and version-control tools exist, naming conventions, the one-line "never do X". Keep them to a few hundred words.
- **Procedures** (`~/.config/bosmang/procedures.md`, under `procedures`) are read only by `/bosmang:close` and `/bosmang:init` when they run. They hold how to *carry things out*: exact commands, entry templates, multi-step routines.

For example, "Work is tracked in Jira through `acli`; never pick a project without asking" is a local rule, while the `acli` command that transitions an item is a procedure. Write procedures as instructions to a session, with the exact commands.

**Tracker: "How do you track work?"**
- **They use a tracker** (Jira, Linear, GitHub Issues, or something else). Ask which CLI sessions should use, then check it's installed and signed in with a read-only command, such as `acli jira auth status`, `gh auth status` or `linear --version`. Record the tool and any "never" rules as local rules, and these as a **Tracker** procedure:
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
- Put the tools and conventions in the local rules, and the exact commands in a **Version control** procedure.

**Closing steps: "When a piece of work closes, what else should happen?"** `/bosmang:close` already checks live state, sums up, records handoffs and reports `[DONE]`. These steps come after it, and go in a **Closing steps** procedure. Offer the usual ones:
- moving the ticket to Done;
- removing the worktree;
- writing a log or journal entry, with its path and format;
- notifying someone.

For each step the user wants, ask whether a session may do it **without asking**, and set the matching authority-matrix row to agree. A closing step and the matrix must never contradict each other.

## 4. The authority matrix

Offer to fork the bundled `authority-matrix.md` to `~/.config/bosmang/authority-matrix.md`; recommend it, since the rows are where the user's own rules belong. Fold in what step 3 settled, such as ticket transitions and worktree removal. Then walk through the remaining "Ask" rows. Change only what the user says to change.

## 5. Write and validate

Write `config.json` with only the keys chosen, since the defaults cover the rest. Then:

- Run `charter.py --check`. It must report `ok`; fix it and run it again until it does. If it notes that the injected text is over budget, move commands, templates and routines out of the local rules into the procedures file.
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

List each finding with its file and line, and propose one of: delete it, move it into the local rules or the procedures (a skill's closing ritual usually becomes Closing steps), or leave it and change the matrix to match. Change nothing until the user says. If open handoffs live only in a running session's context, have that session record them with `ledger.py handoff add` before anything is restarted or retired.

## 7. Close down the old crew

Sessions started before this run have old rules in context and no standing orders, so init closes them down before the coordinator starts. Nothing a session knows may be lost on the way.

1. **List them.** Run `claude agents --json`, and leave out this session (its `sessionId` is `$CLAUDE_CODE_SESSION_ID`). Show each one's `name`, `kind` (interactive or background), `cwd` and `status`, and ask which to close down. Recommend all of them, including any old coordinator.
2. **Save their state.** Send each chosen session one message with `SendMessage`, giving the ledger script's absolute path, since an old session may not have bosmang loaded:
   - record every open handoff with `ledger.py handoff add`, and the scope it owns, if any, with `ledger.py lead open`;
   - then reply with what it recorded, and stop work.

   Wait for the replies, then run `ledger.py list` to confirm. If a session hasn't replied, say which, and ask the user whether to go on without it.
3. **Stop them.** Show the user the final list, and ask once before stopping any of them.
   - Background: `claude stop <id>`. The conversation is kept.
   - Interactive: these can't be stopped from here. Ask the user to `/exit` each one, and wait until `claude agents --json` no longer lists it. Never kill a process.
   - Older sessions have no SessionEnd hook, so mark each one's lead as ended yourself: pipe `{"session_id": "<sessionId>", "cwd": "<cwd>", "reason": "other"}` into `ledger.py session-end-hook`. The ledger then shows its scope as orphaned rather than live.

## 8. Start the coordinator

From the directory chosen in step 2, run `claude --bg --agent bosmang:coordinator -n <coordinator name> "Run the ledger list and report what is open."`. `--agent` applies only when a session is created, which is why the coordinator is always a new session. If it refuses with "Workspace not trusted", ask the user to run `claude` in that directory once and accept the prompt, then try again.

Record it, so `/bosmang:resume` can bring the same session back: take its `sessionId` from `claude agents --json`, then run `ledger.py coordinator set --name <coordinator name> --session-id <sessionId> --cwd <directory>`.

## 9. Bring the crew back

Run `/bosmang:resume`. It finds the coordinator running and offers to resume the leads stopped in step 7. Then tell the user:
- `claude attach <coordinator name>` opens the coordinator; `claude agents` shows every session.
- `/bosmang:resume` brings the crew back after any restart; `/bosmang:lead <SCOPE>` starts new work; `/bosmang:close` finishes it.
