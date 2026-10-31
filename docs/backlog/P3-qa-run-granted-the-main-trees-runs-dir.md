---
by: qa (consistency-check)
---
# QA runs are granted the main tree's `.delivery-team/runs/`, outside the charter's confinement list

*Line numbers are at `547befb`.*

**What's wrong:** so that QA can read the gate log, the orchestrator grants
every QA run the main working tree's `.delivery-team/runs/` directory as an
extra directory. The charter's list of grants does not include it. Approvals
are bypassed inside every grant, so the grant also lets a QA run write there.

**Spec (canonical):**
- `docs/team-charter.md#engines--any-coding-cli-through-an-adapter`
  (lines 151-157): "Every run, on every engine, is confined the same way: its
  working directory plus the explicit directories the orchestrator grants (the
  repository's git common directory, and for a Reviewer the item worktrees
  under review). Confinement is the orchestrator's … approvals are bypassed
  inside that boundary".
- `docs/team-charter.md#scoped-writers-to-the-main-working-tree`
  (lines 253-255): "**no role writes the main tree at all**: a role writes
  only the worktree it was confined to".
- The charter makes the writers rule a floor rule that no role file
  overrides (lines 8-9).
- `docs/architecture.md#invariants`, invariant 9 (lines 100-101): a role
  "never writes outside the worktree it was given".

**Contradicting side:**
- `bin/sdt:1747` calls `start_run("qa", …, extra_dirs=[self.p.runs_dir])`.
- `runs_dir` is `<repo>/.delivery-team/runs` (`bin/sdt:667`). It holds
  `sdt.pid`, every run's prompt and log, and the install markers.
- `bin/sdt:1722` writes the gate log there.
- `roles/qa.md:47-48` relies on the grant: "the gate's full log is at
  `log_path` (readable to you)".
- The in-review branch `item/P1-failed-role-runs-not-retried-or-escalated`
  keeps the same grant when it re-dispatches QA.

**Canonical resolution:** the charter's enumeration and its writers floor
rule. QA reads the log from inside its own confinement.

If a read-only view into the main tree is wanted instead, that is an owner
call, and the charter must name it. It would also have to settle entry 9 of
`P3-restatements-contradict-owning-sections`, which proposes "the main
working tree is never a granted directory".

**Consequence:**
- Every QA run, on every engine, can overwrite or delete the orchestrator's
  own runtime state in the main tree: `sdt.pid`, other runs' logs and
  results.
- The charter's confinement statement is false for one role, and nothing
  says so.

**Acceptance criteria:**
- A QA run's grants are exactly the charter's: the git common directory.
- The QA run can still read the full gate log, at the path `log_path` names
  in `REGRESSION-REQUEST`.
- `tests/test_units.py` asserts that the QA run's add-dirs hold only the git
  common directory, and that the file at `log_path` sits inside the QA run's
  working directory.

**Exact files to change:**
- `bin/sdt`: `run_qa_gate`, plus the QA re-dispatch in `on_qa` once the P1
  item lands.
- `tests/test_units.py`.
- `roles/qa.md`, only if its wording about the log's location changes.

**Suggested approach:** after resetting the QA worktree, copy the gate log
into it and pass that path as `log_path`. The worktree's `git clean -fd` on
the next reset removes the copy, so copies never accumulate. Keep the
`runs/` copy for the owner's inspection.
