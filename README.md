# bosmang

Standing orders for a crew of long-lived Claude Code sessions.

When you run many Claude Code sessions at once, the hard part is not the messaging; Claude Code has had that built in since cross-session messaging arrived. The hard part is your attention. Sessions ask you to approve things you already delegated, relay each other's trivia into your terminal, and lose track of what they were handed when they compact. bosmang is a written charter, plus a little machinery, that keeps the crew out of your way:

- **One coordinator** tracks every scope in flight and keeps the ledger. It is explicitly not an approval gate: it cannot approve anything, and it never relays an instruction as if it came from you.
- **Project leads** each own one scope until you close it, and make every execution decision inside it.
- **Teammates** are authorised for the step they were spawned to do.
- **An authority matrix** says, row by row, which role may do what without asking you.
- **Typed messages** (`[DONE]` `[STATE]` `[COLLISION]` `[CORRECTION]` `[REQUEST]` `[NEEDS-HUMAN]`) let the coordinator decide mechanically what reaches you, and keep the coordinator in charge of meta-coordination: facts go straight to the session they affect, while needs and disputes between scopes go to the coordinator, which routes and settles them, so you never carry messages between sessions. `[NEEDS-HUMAN]` must cite the matrix row that makes it your call.
- **An append-only ledger** of leads and handoffs outlives any session's context.

*Bosmang* is Belter Creole for "boss", from *The Expanse*. In this crew, the bosmang is you.

## Install

```bash
claude plugin marketplace add tthyer/bosmang
claude plugin install bosmang@bosmang --scope user
```

A `SessionStart` hook injects the standing orders into every session, in every repo, and again after `/clear` and compaction.

Two more hooks keep the ledger honest without deciding anything. When a session ends in a lead's worktree, the lead is marked **orphaned**. When a session starts there again, for example on `--resume`, it takes the lead back. `/clear` and headless `claude -p` runs are ignored. Ending a session never closes a scope; only `/bosmang:close` does.

## Configure

Run `/bosmang:init` in any session. It asks how you track work (your tracker and its CLI, or bosmang's ledger), how you version code (git, with `gh` if you use GitHub), what should happen when work closes, who you are and what to call the coordinator. It writes the config and a local-rules file, forks the authority matrix, and validates everything. Then it finds older rules, memories and skills that would contradict the orders, including any skill that acts where your matrix says "Ask".

Or do it by hand. Everything is optional. Without config, the orders refer to "the human" and "coordinator". Write `~/.config/bosmang/config.json`, or point `$BOSMANG_CONFIG` at a file:

```json
{
  "owner": "Ada",
  "coordinator": "nagata",
  "ledger_dir": "~/notes/crew",
  "authority_matrix": "~/notes/crew/authority-matrix.md",
  "append": ["~/notes/crew/local-rules.md"]
}
```

- `authority_matrix` replaces the [bundled matrix](plugins/bosmang/authority-matrix.md). Fork it; the rows are where your own rules belong.
- `append` adds your own markdown after the orders: tracker conventions, infrastructure rules, anything specific to where you work.

To validate the config, and to see exactly what your sessions will read:

```bash
python3 plugins/bosmang/scripts/charter.py --check
python3 plugins/bosmang/scripts/charter.py --print
```

## Use

- **Coordinator:** start a fresh session with `claude --agent bosmang:coordinator -n <coordinator>`. `--agent` applies only when a session is created; resuming an existing session with it doesn't change its agent.
- **Lead:** in any session, `/bosmang:lead EPIC-123`. This registers the session in the ledger and tells the coordinator.
- **Close:** `/bosmang:close` checks the work really is closed, sums it up (shipped, verified, unverified), records what's left as handoffs, closes the lead, reports `[DONE]`, then runs your own closing steps from the local rules.
- **Ledger:** `python3 plugins/bosmang/scripts/ledger.py list`.

Stdlib Python only. No venv, no install.

## Prior art

Claude Code's [agent teams](https://code.claude.com/docs/en/agent-teams) and cross-session messaging provide the transport, and the cross-session docs already say a peer message is never consent. [agent-team](https://github.com/fayerman-source/agent-team) and [claude-team](https://github.com/grgrwlkr/claude-team) arrived independently at "a relay is not approval". [Gas Town](https://github.com/gastownhall/gastown) has a crew hierarchy and a ledger. bosmang adds the layer between: a standing coordinator that is not a gate, a lead tier, and a written authority matrix that decides what interrupts you.

## Tests

```bash
python3 -m unittest discover -s tests
```
