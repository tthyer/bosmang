---
name: lead
description: Make this session the project lead for one scope (an epic, ticket or workstream). It registers the session in the bosmang ledger and announces it to the coordinator. Use when the human says "you're the lead for X", "make this session the lead for X", "take over X", or "/bosmang:lead X". Closing a scope is /bosmang:close.
---

# lead

The standing orders, loaded at session start, define the project-lead role and give the ledger command. This skill is the start and finish of holding that role.

## Start

1. Take the scope key from the human's request: an epic or ticket key, or a short slug. If none is given, ask for one. Don't invent it.
2. Check the ledger's `list` output. If another session already leads this scope, stop and tell the human which session it is. If that lead is ORPHANED, its session has ended, and this session may take the scope over by registering below.
3. If the work needs its own branch, create the worktree with the human's usual tool, then rename the session after the worktree (`/rename <worktree-name>`) so the name says where it acts.
4. Register: `lead open --scope <KEY> --session <this session's name> --worktree "$(git rev-parse --show-toplevel)" [--branch …]`. Always pass `--worktree`. The session hooks know this lead by its session ID: when this session ends, the lead is marked orphaned, and when it is resumed, from any directory, it takes the lead back. The worktree is how `/clear` hands the lead to the session that replaces this one, and how a lead recorded without a session ID is recognised. Running this skill in a new session is how that session takes a scope over. Give each lead its own worktree; two leads registered to one checkout get each other's events.
5. If the coordinator is listed in `ListAgents`, send it `[STATE] <KEY> lead started: <session>, <one line on the scope>`.

## To-do list

A lead keeps one to-do file for its scope, where the human's procedures say. If they name no place, ask. Keep it outside the worktree, which is removed after merge.

- A header line, `Last checked live: <date>`. Sections Open, Blocked, Parked and Done.
- Items are numbered `**N.**` and never renumbered, since others say "waits on N". Each says what done means and what it waits on.
- An item that involves another session cites its ledger handoff ID, and the handoff is updated as the item moves.
- The human edits it too: re-read it before every edit, and never untick their ticks.
- Tick an item only after checking it live, not from a peer's report, then move it to Done with the evidence.
- At `/bosmang:close`, every item still open becomes a handoff.

## Finish

Only when the human says the scope is closed (a merged PR is not enough), run `/bosmang:close` for the scope. When your PR merges, ask whether it is, once, and record the question with `ledger.py question add`, so the scope isn't left open when this session ends. It records the handoffs, closes this lead and reports `[DONE]`.
