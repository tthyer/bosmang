---
name: lead
description: Make this session the project lead for one scope (an epic, ticket or workstream). It registers the session in the bosmang ledger and announces it to the coordinator. Use when the human says "you're the lead for X", "make this session the lead for X", "take over X", or "/bosmang:lead X". Also closes a lead when they say the scope is done.
---

# lead

The standing orders, loaded at session start, define the project-lead role and give the ledger command. This skill is the start and finish of holding that role.

## Start

1. Take the scope key from the human's request: an epic or ticket key, or a short slug. If none is given, ask for one. Don't invent it.
2. Check the ledger's `list` output. If another session already leads this scope, stop and tell the human which session it is.
3. If the work needs its own branch, create the worktree with the human's usual tool, then rename the session after the worktree (`/rename <worktree-name>`) so the name says where it acts.
4. Register: `lead open --scope <KEY> --session <this session's name> [--branch …] [--worktree …]`.
5. If the coordinator is listed in `ListAgents`, send it `[STATE] <KEY> lead started: <session>, <one line on the scope>`.

## Finish

Run this only when the human says the scope is closed. A merged PR is not enough.

1. For anything left undone, run `handoff add`, one item per handoff, with a suggested owner.
2. `lead close --scope <KEY>`.
3. Send the coordinator `[DONE] <KEY> closed: <one line>, <n> handoffs in the ledger`.
