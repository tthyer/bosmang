# bosmang

Standing orders for a crew of long-lived Claude Code sessions.

When you run many Claude Code sessions at once, the hard part is not the messaging; Claude Code has had that built in since cross-session messaging arrived. The hard part is your attention. Sessions ask you to approve things you already delegated, relay each other's trivia into your terminal, and lose track of what they were handed when they compact. bosmang is a written charter, plus a little machinery, that keeps the crew out of your way:

- **One coordinator** tracks every scope in flight and keeps the ledger. It is explicitly not an approval gate: it cannot approve anything, and it never relays an instruction as if it came from you.
- **Project leads** each own one scope until you close it, and make every execution decision inside it.
- **Teammates** are authorised for the step they were spawned to do.
- **An authority matrix** says, row by row, which role may do what without asking you.
- **Typed reports** (`[DONE]` `[STATE]` `[COLLISION]` `[CORRECTION]` `[NEEDS-HUMAN]`) let the coordinator decide mechanically what reaches you. `[NEEDS-HUMAN]` must cite the matrix row that makes it your call.
- **An append-only ledger** of leads and handoffs outlives any session's context.

*Bosmang* is Belter Creole for "boss", from *The Expanse*. In this crew, the bosmang is you.

## Install

```bash
claude plugin marketplace add tthyer/bosmang
claude plugin install bosmang@bosmang --scope user
```

A `SessionStart` hook injects the standing orders into every session, in every repo, and again after `/clear` and compaction.

## Configure

Everything is optional. Without config, the orders refer to "the human" and "coordinator". Write `~/.config/bosmang/config.json`, or point `$BOSMANG_CONFIG` at a file:

```json
{
  "owner": "Ada",
  "coordinator": "nous",
  "ledger_dir": "~/notes/crew",
  "authority_matrix": "~/notes/crew/authority-matrix.md",
  "append": ["~/notes/crew/local-rules.md"]
}
```

- `authority_matrix` replaces the [bundled matrix](plugins/bosmang/authority-matrix.md). Fork it; the rows are where your own rules belong.
- `append` adds your own markdown after the orders: tracker conventions, infrastructure rules, anything specific to where you work.

To see exactly what your sessions will read:

```bash
python3 plugins/bosmang/scripts/charter.py --print
```

## Use

- **Coordinator:** start one long-lived session as the coordinator agent and name it to match `coordinator`. *Unverified:* `claude --agent bosmang:coordinator`.
- **Lead:** in any session, `/bosmang:lead EPIC-123`. This registers the session in the ledger and tells the coordinator. Say the scope is closed and the lead records its handoffs and deregisters.
- **Ledger:** `python3 plugins/bosmang/scripts/ledger.py list`.

Stdlib Python only. No venv, no install.

## Prior art

Claude Code's [agent teams](https://code.claude.com/docs/en/agent-teams) and cross-session messaging provide the transport, and the cross-session docs already say a peer message is never consent. [agent-team](https://github.com/fayerman-source/agent-team) and [claude-team](https://github.com/grgrwlkr/claude-team) arrived independently at "a relay is not approval". [Gas Town](https://github.com/gastownhall/gastown) has a crew hierarchy and a ledger. bosmang adds the layer between: a standing coordinator that is not a gate, a lead tier, and a written authority matrix that decides what interrupts you.

## Tests

```bash
python3 -m unittest discover -s tests
```
