---
by: qa (consistency-check)
---
# QA is told an ENVIRONMENT ruling stops the paging, but a failure with no failure line is never filtered

*Line numbers are at `f323552`.*

**What's wrong:** `roles/qa.md` tells QA that once it rules `ENVIRONMENT`, "the same red never pages anyone again". Since 6d1a554, the charter makes a failing command whose output has no failure line (or that exits on a signal) always new, whatever the known-failures file holds. So an `ENVIRONMENT` ruling on such a failure is written to the file but never filters anything. QA is paged again on every landed tip, and nothing in the role tells it so. The same section also gives two different rulings for a reproducing crash from a layer this environment cannot run.

**Spec (canonical):**
- `docs/team-charter.md#message-schemas--the-canonical-payload-table`, the `REGRESSION-REQUEST` row (line 619): the orchestrator "filters the known-failures file failure by failure: a failing command is filtered only when every failure line in its output holds a known pattern, and one with no failure line or killed by a signal is always new".
- That rule was chosen on purpose, to fail closed (`P1-known-failure-pattern-masks-new-failures`, landed in 6d1a554). The message table is the normative owner. The role's sentence is an incidental restatement.

**Contradicting side:**
- `roles/qa.md#root-cause-then-rule`, the ENVIRONMENT bullet (lines 62-66): "Infra flake, owner-environment fault, a layer this environment cannot run (the profile's Verification environment says which) → `ENVIRONMENT`. Return known-failure patterns … the orchestrator records them in the known-failures file so the same red never pages anyone again." The promise is unconditional.
- The crash bullet (lines 74-79) covers only a crash that "did not reproduce": "The gate never filters a crash (no failure line, or an exit above 128), so a recurrence comes back to you to rule afresh." Nothing says what an `ENVIRONMENT` ruling on a no-failure-line failure does.
- By the role's own definition (lines 38-40), any "nonzero exit with no parsed failures" is in the crash class. A missing tool or an unrunnable layer that prints no `FAIL`/`ERROR`/`error:` line falls there. The crash bullet then says "If it reproduces, it is a regression against the tip". The ENVIRONMENT bullet says the same fault is `ENVIRONMENT`. A layer this environment cannot run always reproduces.

**Code (matches the charter, so it is not the defect):**
- `bin/sdt:716-720` (`new_failure`): an exit above 128 or below 0, or output with no `FAILURE_LINE` match, returns a reason ("no failure line to match against the known failures"), so the command is a new failure.
- `bin/sdt:1153-1171` (`record_known_failures`) appends the patterns and commits them. The `qa-environment` event says "recorded in .delivery-team/known-failures.txt".
- `bin/sdt:2065-2072`: the ruling releases the failure signature. The next red with the same failing command reaches QA again (`bin/sdt:2010`).

**Verified (run by this audit):** in a scratch copy of `f323552`, a test built on `gate_orchestrator`, `land_outside` and `until_gated` (tests/test_units.py) did the following:
- It used a full gate of `test ! -e red.txt || { echo "sh: gpu-probe: command not found"; exit 127; }`.
- It landed `red.txt` outside the run, and the gate dispatched one `REGRESSION-REQUEST`.
- It fed `on_qa` the result `ENVIRONMENT {patterns: ["gpu-probe: command not found"], reason: "no GPU tooling here"}`. The event read `<tip>: recorded in .delivery-team/known-failures.txt`.
- It landed another commit. That tip's gate log read `[exit 127]` then `(new failure: no failure line to match against the known failures)`, and a second `REGRESSION-REQUEST` was dispatched. The QA state read `red at <tip>: 1 new failure(s)`.

**Canonical resolution:** the charter row stands: a failure with no failure line is always new. The role must stop promising that a ruling on one sticks, and must tell QA what to do when such a fault will recur. Letting a ruling filter a no-failure-line failure would re-decide the charter row. That is an owner call and out of scope here.

**Consequence:**
- A consuming project whose full gate includes a layer its profile's Verification environment says cannot run gets a frontier-tier QA run on every landed tip, if that layer fails with no failure line (a missing binary, a refused connection printed without `error:`). The board's QA state also goes red on each of those tips.
- Each such QA run follows a role text that promises the opposite. It has two bullets that rule the reproducing fault two ways.

**Acceptance criteria:**
- The ENVIRONMENT bullet no longer promises unconditionally that the same red never pages again. It says the promise holds only when the failure prints failure lines for the patterns to cover.
- The crash bullet says that an `ENVIRONMENT` ruling on a failure with no failure line (or a signal exit) records patterns that cannot take effect, so the failure comes back on every tip it reaches. When the fault will recur (a layer this environment cannot run, a tool missing from it), QA's `reason` names what the owner must repair: the environment, or that command in `[gate] full`.
- A reproducing crash whose cause is one the ENVIRONMENT bullet names (the profile's Verification environment lists its layer as unrunnable) is ruled `ENVIRONMENT`, not `REGRESSION`. The two bullets no longer rule it two ways.
- Nothing in `roles/qa.md` contradicts the charter's `REGRESSION-REQUEST` row.
- This is a text-only change with no test surface (profile, Quality gate → Not covered).

**Exact files to change:** `roles/qa.md`.

**Suggested approach:**
- ENVIRONMENT bullet: "… the orchestrator records them in the known-failures file, so the same red does not page anyone again, provided it prints failure lines for the patterns to cover (a failure that prints none is never filtered; see the next bullet)."
- Crash bullet: "If it reproduces and its cause is not one the bullet above names, it is a regression against the tip … The gate never filters a crash (no failure line, or an exit above 128), whatever the known-failures file holds, so a recurrence comes back to you on every tip it reaches, and an `ENVIRONMENT` ruling on one records patterns that cannot take effect. When the fault will recur, say in `reason` what the owner must repair: the environment, or that command in `[gate] full`."
