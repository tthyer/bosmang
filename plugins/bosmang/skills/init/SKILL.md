---
name: init
description: Set up bosmang for this user. Asks how they track work and versions, who they are and what to call the coordinator. Drafts the config, short local rules, a procedures file (tracker, version control, closing steps) and a forked authority matrix, which the user installs with one command; lists the permission rules their no-ask steps need; finds older rules and skills that would conflict, then closes down the running sessions and starts the coordinator. Use when the user says "set up bosmang", "bosmang init", "/bosmang:init", "configure bosmang", or changes their tracker, tools or coordinator. Re-runnable, and it starts from the current config.
---

# init

Run every script below with `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/<script>"`. If that variable is empty in your shell, the ledger command in the standing orders gives you the absolute path to the same `scripts/` directory.

Ask **one question at a time**, and offer a recommended answer where there is one. Before asking about a tool, check what's already installed and signed in, so the question can say what you found.

**Never write the user's config yourself.** Draft every file in a directory you can write without prompting (your scratchpad if the session lists one, otherwise one from `mktemp -d`), and in step 5 the user installs the whole draft with one command. The standing orders say what every session may do without asking, so changing them is the user's step, and permission checks rightly stop a session that widens its own authority. One command keeps it to one step, not a wall of approvals.

## 1. Read what exists

Run `charter.py --check`. If a config exists, show it and the local-rules file it points to, and ask what the user wants to change; don't start over. Copy the existing files into the draft directory and edit the copies. A file that is a symlink is kept somewhere deliberate (often a dotfiles repo); `--install` writes through the link, so leave that to it.

## 2. The basics

1. **"How would you like to be addressed?"** Ask this first, and in these words. The answer becomes `owner`, the name every session uses for the human in the standing orders and in reports. Don't propose a name taken from git or the OS account; a username isn't how someone wants to be addressed. Then ask whether sessions should refer to them with particular pronouns. If they give some, write one line into the local rules, such as "Refer to Ada as she/her." If not, sessions use the name, or "they".
2. **Coordinator name:** a session name to use with `-n`. Recommend `nagata`. It must not match a running session that isn't the coordinator, so check `ListAgents`. Then ask which directory it should run in (recommend the current one). Its project memory belongs to that directory, so pick one the user won't move.
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

Write each command a session may run without asking as **one plain command**, never chained with `&&` or `;` (for example `git -C <repo> commit …` and `git -C <repo> push` as separate lines). Step 6 turns these into permission rules, and a rule matches one command.

## 4. The authority matrix

Offer to fork the bundled `authority-matrix.md` into the draft (it installs to `~/.config/bosmang/authority-matrix.md`); recommend it, since the rows are where the user's own rules belong. Fold in what step 3 settled, such as ticket transitions and worktree removal. Then walk through the remaining "Ask" rows. Change only what the user says to change.

## 5. Install

Write `config.json` into the draft with only the keys chosen, since the defaults cover the rest. Every path in it is the file's **final** path (`~/.config/bosmang/local-rules.md`), not the draft's. Never put a path into the plugin's install directory in any file: it contains the version number and breaks on the next update. Refer to a script as "`charter.py`, beside the ledger command in the standing orders" instead.

Then show the user, in one message:
- the roles section, the authority table and their local rules, as their sessions will see them (`BOSMANG_CONFIG=<draft>/config.json charter.py --print` renders the draft);
- every matrix row that lets a session act **without asking**, marked, since those widen what sessions may do;
- the one command that installs it all, for them to run with the `!` prefix:

  ```
  ! python3 "<scripts>/charter.py" --install <draft>
  ```

`--install` refuses a draft with problems and installs nothing; fix the draft and give them the command again. It backs up anything it replaces, writes through symlinks, and finishes with `--check`. If that notes the injected text is over budget, move commands, templates and routines from the local rules into the procedures, and install again.

## 6. Permissions for what sessions do without asking

A row that says "Yes" is not enough on its own: Claude Code's permission prompts, and auto mode's checks, still stop a command no setting allows. Closing steps are where this bites, such as committing and pushing a log entry, so a setup that leaves them out makes every close stop for approval or be refused.

For each command a procedure runs without asking, give the user the rule that allows it, and tell them:
- the rules go in their **global** settings, `~/.claude/settings.json`, under `permissions.allow`. If the file doesn't exist, they create it with `{"permissions": {"allow": [ … ]}}`;
- each rule names one command narrowly, such as `Bash(git -C /path/to/journal-repo push:*)`. Auto mode honours narrow rules before its own checks, but sends broad ones such as `Bash(git:*)` through them anyway;
- these are theirs to add, in their editor or with `/permissions`. A session adding rules that widen its own permissions is what auto mode exists to stop.

## 7. Retire what conflicts

Older rules and skills that contradict the orders will win, because they're more specific and are loaded right when the work happens. Search all of these:

- **Instructions:** the global `CLAUDE.md` and every file it imports, plus any `CLAUDE.md` or `CLAUDE.local.md` in the current repo and its `.claude/rules/`.
- **Memory:** the memory directory for this project.
- **Skills and agents:** `~/.claude/skills/`, `~/.claude/agents/`, the repo's `.claude/skills/` and `.claude/agents/`, and the skills of every other installed plugin (under `~/.claude/plugins/marketplaces/*/plugins/*/skills/`).

Look for anything that:
- names a coordinator, or tells sessions to report or hand off somewhere other than the ledger;
- closes, wraps up or hands off a thread;
- **acts where the matrix says "Ask"**, or asks where the matrix says "Yes". Check for pushes, merges, ticket transitions, worktree removal, production writes and posting to people.

List each finding with its file and line, and propose one of: delete it, move it into the local rules or the procedures (a skill's closing ritual usually becomes Closing steps), or leave it and change the matrix to match. Change nothing until the user says. If open handoffs live only in a running session's context, have that session record them with `ledger.py handoff add` before anything is restarted or retired.

## 8. Close down the old crew

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

## 9. Start the coordinator

From the directory chosen in step 2, run `claude --bg --agent bosmang:coordinator -n <coordinator name> "Run the ledger list and report what is open."`. `--agent` applies only when a session is created, which is why the coordinator is always a new session. If it refuses with "Workspace not trusted", ask the user to run `claude` in that directory once and accept the prompt, then try again.

Record it, so `/bosmang:resume` can bring the same session back: take its `sessionId` from `claude agents --json`, then run `ledger.py coordinator set --name <coordinator name> --session-id <sessionId> --cwd <directory>`.

## 10. Bring the crew back

Run `/bosmang:resume`. It finds the coordinator running and offers to resume the leads stopped in step 8. Then tell the user:
- `claude attach <coordinator name>` opens the coordinator; `claude agents` shows every session.
- `/bosmang:resume` brings the crew back after any restart; `/bosmang:lead <SCOPE>` starts new work; `/bosmang:close` finishes it.
