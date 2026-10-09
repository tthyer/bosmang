# bosmang

Standing orders for a crew of long-lived Claude Code sessions.

When you run many Claude Code sessions at once, the hard part is not the messaging; Claude Code has had that built in since cross-session messaging arrived. The hard part is your attention. Sessions ask you to approve things you already delegated, relay each other's trivia into your terminal, and lose track of what they were handed when they compact. bosmang is a written charter, plus a little machinery, that keeps the crew out of your way:

- **One coordinator** tracks every scope in flight and keeps the ledger. It is explicitly not an approval gate: it cannot approve anything, and it never relays an instruction as if it came from you.
- **Project leads** each own one scope until you close it, and make every execution decision inside it.
- **Teammates** are authorised for the step they were spawned to do.
- **An authority matrix** says, row by row, which role may do what without asking you.
- **Typed messages** (`[DONE]` `[STATE]` `[COLLISION]` `[CORRECTION]` `[REQUEST]` `[NEEDS-HUMAN]`) let the coordinator decide mechanically what reaches you, and keep the coordinator in charge of meta-coordination: facts go straight to the session they affect, while needs and disputes between scopes go to the coordinator, which routes and settles them, so you never carry messages between sessions. `[NEEDS-HUMAN]` must cite the matrix row that makes it your call.
- **An append-only ledger** of leads, handoffs, questions waiting on you and standing notices outlives any session's context.

*Bosmang* is Belter Creole for "boss", from *The Expanse*. In this crew, the bosmang is you.

**Status: early.** bosmang has been used in one real work setup: Jira through `acli`, git and GitHub through `gh`, worktrees through worktrunk. `/bosmang:init` also handles other trackers, and tracking work in the ledger alone, but neither has been run for real yet. It builds on Claude Code features that are still experimental or in preview: [agent teams](https://code.claude.com/docs/en/agent-teams), [cross-session messaging](https://code.claude.com/docs/en/cross-session-messaging) and [background sessions](https://code.claude.com/docs/en/agent-view). Expect rough edges, and please file what you hit.

## Design rule: decide, don't do

Everything injected at session start is paid for in every session's context, every time. So bosmang injects only what changes how a session **decides**: the roles, the authority matrix, the message tags, the test for interrupting you, and a few local rules. How to **carry something out** (exact commands, templates, closing routines) goes in a procedures file that skills read only when they run. `charter.py --check` reports what is injected against a 7,000-character budget. Claude Code also shows at most 10,000 characters of any one hook's output in full, and replaces anything longer with a 2KB preview.

## Install

```bash
claude plugin marketplace add tthyer/bosmang
claude plugin install bosmang@bosmang --scope user
```

A `SessionStart` hook injects the standing orders, and any open standing notices, into every session, in every repo, and again after `/clear` and compaction.

Two more hooks keep the ledger honest without deciding anything. When a lead's own session ends, the lead is marked **orphaned**. When that session comes back with `--resume`, from any directory, it takes the lead back. Another session starting in the worktree takes nothing; a new session takes a scope over with `/bosmang:lead`. `/clear` and headless `claude -p` runs are ignored. Ending a session never closes a scope; only `/bosmang:close` does.

## Configure

Run `/bosmang:init` in any session. It asks how you track work (your tracker and its CLI, or bosmang's ledger), how you version code (git, with `gh` if you use GitHub), what should happen when work closes, who you are and what to call the coordinator. It drafts the config, local rules, procedures and your copy of the authority matrix, and you install them with one command (`charter.py --install <draft>`). Changing what sessions may do is your step, not a session's. It also lists the permission rules (for your global `~/.claude/settings.json`) that the steps you've allowed without asking need, so permission prompts and auto mode don't stop them. Then it finds older rules, memories and skills that would contradict the orders, including any skill that acts where your matrix says "Ask".

Or do it by hand. Everything is optional. Without config, the orders refer to "the human" and "coordinator". Write `~/.config/bosmang/config.json`, or point `$BOSMANG_CONFIG` at a file:

```json
{
  "owner": "Ada",
  "coordinator": "nagata",
  "ledger_dir": "~/notes/crew",
  "authority_matrix": "~/notes/crew/authority-matrix.md",
  "append": ["~/notes/crew/local-rules.md"],
  "procedures": ["~/notes/crew/procedures.md"]
}
```

- `authority_matrix` replaces the [bundled matrix](plugins/bosmang/authority-matrix.md). Fork it; the rows are where your own rules belong.
- `append` adds short local rules after the orders, such as which tools you use and what never to do. They're injected into every session, so keep them brief.
- `procedures` holds how-to detail: tracker and version-control commands, and the **Closing steps** that `/bosmang:close` runs. It isn't injected; skills read it with `charter.py --procedures`.

These files are yours. They instruct every session, so sessions never edit them: a session that wants a change drafts it in a new directory, with a copy of `config.json`, and gives you the `charter.py --install <draft>` command to run. In auto mode, Claude Code may also block a session's direct write to them as instruction poisoning.

To validate the config, and to see exactly what your sessions will read:

```bash
python3 plugins/bosmang/scripts/charter.py --check
python3 plugins/bosmang/scripts/charter.py --print
```

## Use

- **Coordinator:** `/bosmang:init` starts it as a background session, after closing down the sessions already running; open it with `claude attach <coordinator>`. To start one by hand: `claude --bg --agent bosmang:coordinator -n <coordinator>`. `--agent` applies only when a session is created; resuming an existing session with it doesn't change its agent.
- **Resume:** `/bosmang:resume` brings the crew back after a restart: the coordinator session the ledger records (it keeps its role and history), then any lead whose session ended without closing its scope.
- **Board:** `/bosmang:board` shows what's in flight: the ledger, the live sessions and, if your procedures say how, your tracker and your own dashboard. `update` refreshes it.
- **Lead:** in any session, `/bosmang:lead EPIC-123`. This registers the session in the ledger and tells the coordinator.
- **Close:** `/bosmang:close` checks the work really is closed, sums it up (shipped, verified, unverified), records what's left as handoffs, closes the lead, reports `[DONE]`, then runs your own closing steps from the local rules.
- **Ledger:** `~/.local/share/bosmang/bin/ledger list`. That launcher always runs the newest installed version, so sessions started before an update still reach the new scripts.
  - `handoff update <id>` changes a handoff's item, owner or due date without changing its ID.
  - `question add --scope X --text …` records a question only you can answer, so it is asked once and stays on the board until `question answer <id>`.
  - `notice add --text … --from …` records a rule for the whole crew. Every session gets it at start until `notice close <id>`.
- **Precedence:** your direct instruction in a session overrides any standing rule or notice. The session follows it and reports the departure.

## The ledger

The ledger is a set of append-only JSONL files in `ledger_dir`: `leads.jsonl`, `handoffs.jsonl`, `questions.jsonl`, `notices.jsonl` and `coordinator.jsonl`. Each change is one line, written under a file lock, and the current state is the last line for each key. Nothing is ever rewritten, so the files are also the history.

The default, `~/.local/state/bosmang`, has no backup. For history and backup, point `ledger_dir` at a directory in a git repo; the files diff cleanly. bosmang never commits them itself. Add the commit and push to your **Closing steps** so `/bosmang:close` runs them, and `/bosmang:init` offers to do this.

Stdlib Python only. No venv, no install.

## Prior art

**Claude Code** supplies the transport: [cross-session messaging](https://code.claude.com/docs/en/cross-session-messaging), [background sessions](https://code.claude.com/docs/en/agent-view) and [agent teams](https://code.claude.com/docs/en/agent-teams). Both messaging docs already say a peer's message is never consent. An agent team has a lead, but the team lasts only as long as the lead's session. [Projects](https://code.claude.com/docs/en/claude-projects) runs a standing coordinator conversation with its own memory, for cloud threads.

**[Gas Town](https://github.com/gastownhall/gastown)** is the fullest precedent. It has a Mayor that coordinates, a Witness supervising each project, a Beads ledger in git, typed mail, escalation to the human routed by severity, and orphan clean-up. It is a standalone system built on tmux, for several agent runtimes.

**[claude-team](https://github.com/grgrwlkr/claude-team)** has typed messages, per-role limits enforced by a hook (only the integrator merges), and handoffs on disk, for the length of one run. **[agent-team](https://github.com/fayerman-source/agent-team)** has a coordinator that acts as the merge gate, and a hook that enforces state reports. Both say a relayed approval is not approval.

bosmang is smaller than these, and differs in three ways:

- It is a Claude Code plugin made of written orders. There is no daemon, no tmux layer and nothing to run beyond Python's standard library.
- Its coordinator is explicitly not a gate. It tracks, routes and settles disputes between scopes, and approves nothing.
- A written authority matrix, which you fork, decides what interrupts you. It is keyed by role and by action (merge, post to people, write to production), not by tool, and `[NEEDS-HUMAN]` must cite one of its rows. Leads hold their scopes across restarts until you close them.

## Changes and contributing

See [CHANGELOG.md](CHANGELOG.md) and [CONTRIBUTING.md](CONTRIBUTING.md).

## Tests

```bash
python3 -m unittest discover -s tests
```
