---
by: qa (consistency-check)
---
# The full gate runs inside the tick, freezing the ledger, liveness enforcement and the pipeline for its whole duration

*Line numbers are at `547befb`.*

**What's wrong:** `run_qa_gate()` runs every full-gate command synchronously,
inside `tick()`. While the gate runs (up to `qa_gate` seconds per command),
the orchestrator:
- polls no role run, so it enforces no timeout or stall limit;
- writes no ledger;
- dispatches, reviews and lands nothing.

So the board and the statusline both report a healthy run as stale during any
gate longer than 90 seconds.

**Spec (canonical):**
- `docs/team-charter.md#progress-ledger--the-runs-machine-readable-state`,
  lines 303-306: the orchestrator writes the ledger "on **every tick**, not on
  a report cadence — a continuously-rendering surface needs fresh state
  between reports".
- Same section, line 321: `generatedAt` "drives staleness".
- `docs/team-charter.md#role-runs--how-every-role-executes`, lines 121-125:
  "Every run has a wall-clock budget and … a stall limit … The orchestrator
  kills a run that exceeds either".

**Code (the defect):**
- `tick()` calls `run_qa_gate()` at `bin/sdt:1863`.
- `run_qa_gate()` writes the ledger once, with the QA agent's state set to
  "gating", then calls `run_full_gate()` (`bin/sdt:1720-1723`).
- `run_full_gate()` runs each command through `sh()` (`bin/sdt:966-970`).
  `sh()` is a blocking `subprocess.run(..., timeout=qa_gate)`
  (`bin/sdt:68-69`); the default `qa_gate` is 3600 s per command
  (`bin/sdt:144`).
- Timeouts and stalls are enforced only in `RoleRun.poll()`
  (`bin/sdt:588-602`), which `tick()` calls only at its start
  (`bin/sdt:1846-1847`).
- Both consumers treat state older than 90 s as stale:
  `assets/dashboard.html:448` and
  `extras/claude/skills/statusline/statusline.sh:19`.

**Evidence (run by this audit):** in a scratch repo at `5c1e96c` (this code is unchanged at `547befb`), with
`[gate] full = ["sleep 4"]` and `qa_pending_tip` set:
- `Orchestrator.run_qa_gate()` blocked for 4.1 s.
- When it returned, the ledger's latest `generatedAt` was still the
  pre-gate write, 4.5 s old.

This repo's own gate takes about 45 s (`.delivery-team/runs/qa-gate-5c1e96c8.log`),
which is under the 90 s threshold. A consumer with a 10-minute suite is not.

**Consequence:** for a project whose full gate takes minutes:
- every landing freezes the whole run for that long;
- the board shows "Stale" while the run is healthy;
- a hung developer or reviewer run outlives its stall limit by the gate's
  duration;
- a hung gate command freezes the orchestrator for up to an hour per command.

**Acceptance criteria:**
- The full gate runs as a background process that `tick()` polls, the way it
  polls a `RoleRun`.
- While a gate runs, ticks continue: role runs are polled and killed on
  timeout or stall, and the ledger is rewritten every tick.
- The gate still runs its commands in order and fails closed.
- The exclusive-resource wait (`bin/sdt:1707-1709`) and the one-gate-at-a-time
  guard still hold.
- `tests/test_units.py` uses a gate command that sleeps longer than two poll
  intervals and asserts that:
  - `run_qa_gate()` returns promptly;
  - a `tick()` during the gate rewrites `state.json` with a newer
    `generatedAt`;
  - the gate's verdict is applied once the command ends.

**Exact files to change:**
- `bin/sdt`: `run_qa_gate`, `run_full_gate`, `tick`, `drained`.
- `tests/test_units.py`.

**Suggested approach:** hold the gate's progress on the orchestrator (the
current command index, its `Popen`, its log handle) and advance it from
`tick()`. `drained()` must stay false while a gate runs.
`547befb` (`P1-role-worktrees-shared-or-never-reset`) already rewrote
`run_qa_gate`'s worktree handling, so build on its `role_worktree` helper.
