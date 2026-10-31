---
by: qa (consistency-check)
---
# The ledger stamps every agent's `lastSignalAt` with the write time

**What's wrong:** `write_ledger()` sets `lastSignalAt` to `now()` for every
agent row: the orchestrator, every live run, and QA even when idle. So the
board can never show a stalled run as quiet or silent.

**Spec (canonical):**
`docs/team-charter.md#progress-ledger--the-runs-machine-readable-state`
(lines 356-357): "lastSignalAt is epoch seconds of the last real liveness
signal (0/absent = never/idle)."

**Code (the defect):**
- `bin/sdt:1071-1080`: all three kinds of agent row get
  `"lastSignalAt": now()`.
- `RoleRun` already tracks the real signal in `_last_growth`
  (`bin/sdt:550`, `bin/sdt:575-576`).

**Consumer:** `assets/dashboard.html:845-856` buckets agents by
`now - lastSignalAt` into live, quiet (≥120 s) and silent (≥600 s). Because
`lastSignalAt` always equals `generatedAt`, every agent always reads "live".

**Consequence:** the board's stall indicator never fires. An owner watching
the board sees a hung run as live until the stall limit kills it. On a
non-streaming engine, where stall detection is off by design (charter lines
119-122), that never happens.

**Acceptance criteria:**
- A live run's `lastSignalAt` is the last time its log grew. For a
  non-streaming adapter, which is silent until it finishes, that is the run's
  start time.
- An idle QA row omits `lastSignalAt` or sets it to `0`.
- `tests/test_units.py` builds a ledger with a run whose log has not grown and
  asserts its `lastSignalAt` is earlier than `generatedAt`.

**Exact files to change:** `bin/sdt` (`write_ledger`, `RoleRun`),
`tests/test_units.py`.

**Suggested approach:** expose a `RoleRun.last_signal` property that returns
`_last_growth`.
