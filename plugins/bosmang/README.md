# bosmang

Standing orders for a crew of long-lived Claude Code sessions, so you are interrupted only for what is yours to decide.

- **One coordinator** tracks every scope in flight and keeps the ledger. It cannot approve anything, and it never relays an instruction as if it came from you.
- **Project leads** each own one scope until you close it, and make every decision inside it.
- **Teammates** are authorised only for the step they were spawned to do.
- **An authority matrix**, which you fork, says which role may do what without asking you.
- **Typed messages** (`[DONE]` `[STATE]` `[COLLISION]` `[CORRECTION]` `[REQUEST]` `[NEEDS-HUMAN]`) decide what reaches you.
- **An append-only ledger** of leads and handoffs outlives any session's context.

## What it does to every session

A `SessionStart` hook injects the standing orders (`charter.md`, the authority matrix and your local rules) into every session, in every repo, and again after `/clear` and compaction. `/bosmang:init` shows you exactly that text before you install it, and `charter.py --print` shows it any time. `SessionStart` and `SessionEnd` hooks also record in the ledger when a lead's session ends or resumes.

What bosmang reads and writes is listed in [PRIVACY.md](PRIVACY.md). It sends nothing off your machine.

## Use

Run `/bosmang:init` to configure it, then `/bosmang:lead <scope>`, `/bosmang:board`, `/bosmang:close` and `/bosmang:resume`. Full documentation: <https://github.com/tthyer/bosmang#readme>.

Requires Python 3 (standard library only).

MIT licensed.
