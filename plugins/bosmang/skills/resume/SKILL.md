---
name: resume
description: Bring the crew back after a restart, a reboot or a night off. Resumes the coordinator session the ledger records, keeping its role and history, then offers to resume every lead whose session is gone without closing its scope. Use when the user says "resume the crew", "bring everyone back", "start the coordinator", "bosmang resume" or "/bosmang:resume". /bosmang:init ends by running it.
---

# resume

Run every script below with `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/<script>"`. If that variable is empty in your shell, the ledger command in the standing orders gives you the absolute path to the same `scripts/` directory.

A session keeps its agent when it's resumed, so a resumed coordinator is still the coordinator, with everything it knew. `--agent` can't be added to an existing session, so only a session created as the coordinator can be one.

## 1. Read the state

Run `ledger.py list --json` and `claude agents --json`. A session is running if its `sessionId` appears in the second list.

## 2. The coordinator

- **None recorded:** stop, and tell the user to run `/bosmang:init`.
- **Running:** say so, and that `claude attach <name>` opens it.
- **Stopped:** resume it in the background from the directory the ledger records, since `--resume` finds a conversation by directory:

  ```
  cd <cwd> && claude --bg --resume <session_id> "Resumed by /bosmang:resume. Run the ledger list and report what's open."
  ```

  If `claude` can't find the conversation, it was deleted. Then start a new coordinator with the same name, as `/bosmang:init` does (`claude --bg --agent bosmang:coordinator -n <name> …`, from the same directory). Record it with `ledger.py coordinator set --name <name> --session-id <sessionId> --cwd <cwd>`, taking the `sessionId` from `claude agents --json`. Tell the user it's a fresh session: what it knows is what the ledger holds.

## 3. Leads without a running session

These are the unclosed leads whose session isn't running:
- every lead the ledger shows as ORPHANED (its session ended);
- every other lead whose `session_id` isn't in `claude agents --json`. A crash or an abrupt reboot skips the exit hook, so the ledger still shows these leads as live.

List each with its scope, session and worktree, then ask once with `AskUserQuestion`: "Resume all (Recommended)", "Let me pick" (then take the scopes in chat), or "None".

- **With a `session_id`:** `cd <worktree> && claude --bg --resume <session_id> "Resumed by /bosmang:resume. Carry on with your scope."`. The session start hook marks the lead resumed.
- **Without one, or the conversation is gone:** say so. The user can resume it by name with `claude --resume <session>`, or start a new session in the worktree with `/bosmang:lead <SCOPE>`, which takes the scope over.

Don't resume a lead the user has said is finished; offer `/bosmang:close` for it instead.

## 4. Report

Run `ledger.py list`. Tell the user `claude agents` shows every session, and that `claude attach <name>` opens any background one.
