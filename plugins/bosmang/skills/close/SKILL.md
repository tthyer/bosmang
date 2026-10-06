---
name: close
description: Close one scope or thread of work: check it really is closed, sum it up, record what's left in the ledger, close the lead, report [DONE], then run the user's own closing steps. Use when the human says "X is done", "close this out", "wrap up", "sum up", "hand off what's left", or a lead's scope has closed. One thread at a time; not a sweep across sessions.
---

# close

The standing orders, loaded at session start, give the ledger command, the report format and the authority matrix. Your local rules may add **Tracker**, **Version control** and **Closing steps** sections, and where they exist they say how to carry out the steps below.

Ask the human nothing along the way. If a step needs their decision, finish every step that doesn't depend on it, then ask all the open questions together in one `AskUserQuestion` form at the end.

## 1. Read the live state

Earlier turns and peer messages go stale, so check live and never repeat state from memory. Use the commands in your local rules' Tracker and Version control sections. With none, use `git status -sb` and the ledger's `list` output.

If the work isn't actually closed (a PR is still open, a check failed, the branch has unpushed commits), stop and say so. The thread hasn't closed.

## 2. Sum up for the human

Three short parts, in this order:

- **Shipped:** what changed, with PR and ticket named in full.
- **Verified:** what was checked, and against what: real data, tests, or a live run.
- **Unverified:** anything that holds only in theory. If nothing is unverified, say so.

## 3. Record what's left

- `handoff add` once per remaining item, stated so someone else can act on it: what has to happen, how they'll know it worked, and a suggested owner. Add `--due` when it has a date.
- If this session is the registered lead for the scope, `lead close --scope <KEY>`.
- If the coordinator is listed in `ListAgents`, send it one line: `[DONE] <KEY> closed: <one line>, <n> handoffs in the ledger`, or "Nothing remains" in so many words.

Skip anything already done: handoffs already in the ledger, or a `[DONE]` this session already sent for this scope. Say that you skipped it.

## 4. Run the closing steps

Run the **Closing steps** section of your local rules, in order. Each step is still subject to the authority matrix: a step that the matrix marks "Ask" goes into the end-of-run question form instead. Run anything that deletes this session's working directory last.

If there are no closing steps, you're done.

## Common mistakes

| Mistake | Instead |
|---|---|
| Reporting state from earlier turns | Step 1, every time |
| Asking questions one per turn | One form at the end |
| "Handed off" with no list | One actionable `handoff add` per item, or "Nothing remains" |
| Telling the human you sent the `[DONE]` | One line in the summary is enough |
