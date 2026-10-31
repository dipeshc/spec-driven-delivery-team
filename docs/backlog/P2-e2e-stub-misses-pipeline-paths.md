---
by: qa (consistency-check)
---
# The stub end-to-end run does not exercise "every pipeline path"

**What's wrong:** the architecture says the stub-engine e2e run "exercises
every pipeline path without a model". It doesn't:
- the stub Manager never returns `hold` or `research`, and answers every
  `DECISION-REQUEST` with `block`;
- the stub QA always returns `REGRESSION`.

So whole branches of `bin/sdt` run in no test. That is how the `hold` defect
(`P0-held-and-unblocked-items-skip-triage.md`) went unnoticed.

**Spec (canonical):**
- `docs/architecture.md#components` (line 54): "`tests/` | The
  orchestrator's unit tests and an end-to-end run on a scripted stub engine …
  that exercises every pipeline path without a model."
- `docs/architecture.md#changing-this-repo` (lines 113-114): "the tests under
  `tests/` pin the orchestrator's behaviour to what the charter says."

**Code (the gap):**
- `tests/fake_engine.py:102-105`: every `DECISION-REQUEST` is answered with
  `action: block`.
- `tests/fake_engine.py:106-125`: triage returns only `dispatch`, `block` and
  a group.
- `tests/fake_engine.py:67-80`: QA always returns `REGRESSION`.
- `tests/fake_engine.py:83-96`: the Researcher stub exists but is
  unreachable, because no triage decision is `research`.
- `tests/test_e2e.py:15-36` and `81-84`: no slug drives any other path.

**Paths with no test today** (the sibling items `P0-held-and-unblocked-items-skip-triage`,
`P1-failed-role-runs-not-retried-or-escalated`,
`P2-researcher-no-item-never-retires-the-item` and
`P2-sdt-role-drops-notes-and-misnames-consistency-dispatch` already add tests
for their own paths):
- triage `research`, then Researcher `FILED`, then the originating item is
  retired;
- `DECISION` `retry` and `adopt`;
- `REVIEW-ROUNDS-EXCEEDED`;
- Merge-Clerk `MERGE-BLOCKED`;
- a `LANDABLE` sha that is no longer a fast-forward (re-verified on the new
  tip);
- QA `ENVIRONMENT`: the known-failures file is appended and committed, and
  the same red is then filtered.

**Consequence:** the gate stays green while these paths go unverified. The
architecture's claim is what reviewers and the owner rely on to trust the
orchestrator.

**Acceptance criteria:**
- `tests/fake_engine.py` gains slug-driven behaviours for each path listed
  above, and `tests/test_e2e.py` gains assertions for each.
- Afterwards, every `action` and every `message` that the charter's table
  defines for the Manager, Merge-Clerk, QA and Researcher is produced by the
  stub in at least one test.

**Exact files to change:** `tests/fake_engine.py`, `tests/test_e2e.py`.

**Suggested approach:** follow the existing slug-marker pattern (`block-me`,
`dev-blocks`, `twice`, `red`). Add a second `make_repo` scenario if one run
cannot hold every path.
