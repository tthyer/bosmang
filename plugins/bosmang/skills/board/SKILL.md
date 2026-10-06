---
name: board
description: Show what's in flight across the crew, and refresh the user's own dashboard if they keep one. Read mode joins the ledger, the live sessions and the tracker; refresh mode also runs the user's Board procedure, reconciles merged work against the tracker, and checks the work log. Use when the user says "board", "update", "update the board", "threads", "what's in flight", "what's waiting on me", or "what is everyone doing". The coordinator runs it most; any session may read.
---

# board

Run every script below with `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/<script>"`. If that variable is empty in your shell, the ledger command in the standing orders gives you the absolute path to the same `scripts/` directory. Run `charter.py --procedures` first: a **Board** section there, if the user has one, says how their dashboard is read and refreshed, and its commands replace the defaults below.

**Read** is the default and changes nothing. **Refresh** is for "update", or when the user asks for it.

## Read

1. **The crew.** Run `ledger.py list --json` and `claude agents --json`. Join them on session ID:
   - each lead: scope, session, and whether its session is running, idle or gone;
   - running sessions that hold no scope, by name;
   - a lead the ledger calls live whose session isn't running is a finding: say so.
2. **Handoffs**, soonest due first. Name any that are overdue.
3. **The tracker's view**, if the procedures say how to list in-flight items. Show it in the order the tracker holds; never reorder it, since the order is the user's.
4. **Live PR state** for items in flight, in **one** batched call rather than one per PR. Report only what contradicts the board, such as a PR now conflicting or merged.
5. **Age.** Anything read from a cache says how old it is.

Keep it to one short table plus findings. Print an item's background only when asked, and only that item's.

## Refresh

1. Run the **Board** procedure's refresh steps, in its order. A dashboard that publishes to a fixed address keeps that address: publish to it, never to a new one.
2. **Reconcile merged work against the tracker.** List PRs merged since the last refresh, take their item keys, and check each item's status in one query. An item whose PR merged but which isn't Done is stale. Moving it follows the authority matrix: if the matrix says "Ask", gather them into one question ("PRs for X and Y merged; move them to Done?"). A merge doesn't always finish an item: check what the item asks for against what the PR changed, and treat several PRs against one item as work in progress. Leave other people's items alone.
3. **Check the work log**, if the closing steps keep one. Name the closed threads without an entry. A session that is still running writes its own entry: message it rather than writing one for it.

## Never

- Reorder or reprioritise anything.
- Record state only on the dashboard. The ledger is where state lives; the dashboard is a view of it.
