---
by: qa (consistency-check)
---
# A direct-lane landing is never full-gated by a running orchestrator

**What's wrong:** the spec makes the orchestrator's full-gate run on every new
tip the direct lane's independent verification. But the orchestrator gates
only the shas it landed itself. A direct-lane fast-forward made during an
active run is never gated, unless a later team-lane landing happens to sit on
top of it.

**Spec (canonical):**
- `docs/team-charter.md#scoped-writers-to-the-main-working-tree`
  (lines 270-271): "The QA full-gate run on the new tip is this lane's
  independent verification".
- `docs/team-charter.md#message-schemas--the-canonical-payload-table`
  (line 586): "the orchestrator runs the gate itself on every landed tip".
- `roles/qa.md#why-you-exist--the-fail-closed-full-run` (lines 36-38): "The
  full-gate run on every new tip is the independent verification that lane
  depends on."
- `skills/team/SKILL.md#direct-lane--skip-the-team-for-low-risk-work`
  (lines 64-66): "The orchestrator's full-gate run on every new tip is the
  independent verification for this lane when a run is active".

**Code (the defect):** `bin/sdt:1605` is the only place `qa_pending_tip` is
set to a sha, and it runs only in `on_merge_clerk()` after the orchestrator's
own `land()`. `tick()` (`bin/sdt:1765-1784`) never compares the default-branch
tip with the last gated tip.

**Evidence (run by this audit):** with an orchestrator constructed, a direct
commit was made on `main` and `tick()` called. `qa_pending_tip` stayed `''`.

**Consequence:** the direct lane's scoped gate is partial by design (charter,
"Repo-wide invariant guards"), and the full-gate backstop it relies on never
runs. A direct-lane regression lands unverified and is first blamed on
whichever team-lane landing follows it.

**Acceptance criteria:**
- On every tick, any default-branch tip the orchestrator has not gated is
  queued for the full gate exactly as a landed sha is. This excludes tips the
  orchestrator produced through its own housekeeping (backlog filing,
  blocking, known-failures).
- `tests/test_e2e.py` or `tests/test_units.py`: a commit made on the default
  branch during a run, outside the orchestrator, is gated. A red result
  dispatches QA with `last_green_tip` set to the previous green tip.

**Exact files to change:** `bin/sdt` (`tick`, `run_qa_gate`, plus a record of
the last gated or housekeeping tip), `tests/test_e2e.py` or
`tests/test_units.py`.

**Suggested approach:** remember the tip after each orchestrator commit
(landing or housekeeping). In `tick()`, when `self.p.tip()` differs from it
and from `qa_green_tip`, set `qa_pending_tip`.
