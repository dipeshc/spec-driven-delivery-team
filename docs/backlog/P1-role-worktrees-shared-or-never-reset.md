---
by: qa (consistency-check)
---
# Role worktrees are shared by concurrent runs, reset under live runs, or never reset

**What's wrong:** the cadence consistency check runs in the `qa` worktree, and
each of the two roles resets that tree while the other has a live run in it.
The `manager` and `researcher` worktrees are never reset after they are
created, so those roles work at the commit the tree was first cut from, with
whatever an earlier run left behind. Several concurrent Researcher (or
Manager) runs also share one tree.

**Spec (canonical):**
- `docs/team-charter.md#role-runs--how-every-role-executes` (lines 88-91):
  "Every role runs as one headless process … confined to the working
  directory it was given: an item worktree for a Developer, a detached
  worktree for every other role."
- `docs/team-charter.md#branch-and-worktree-naming` (lines 435-437): "The
  persistent `reviewer-<n>`, `merge-clerk` and `qa` worktrees are detached and
  reset to a known-clean state before every run."
- `roles/qa.md#your-dispatch` (lines 46-48): "Your working directory is the
  QA worktree, detached at the failing tip". Lines 54-56 also have QA bisect
  and rerun commands in that tree.
- `roles/consistency-check.md` (line 21): "Your working directory is a
  detached worktree at the tip to audit."
- `roles/researcher.md#your-dispatch` (lines 28-29): "Your working directory
  is a detached scratch worktree at the default branch".

**Code (the defect):**
- `bin/sdt:1634-1635` and `bin/sdt:1661`: the gate and the QA role use `qa`.
- `bin/sdt:1713-1714`: the consistency check calls
  `ensure_detached_worktree("qa")` and then `reset_detached(...)`.
- `bin/sdt:1621` guards the gate only against a live `qa` run, and
  `bin/sdt:1707` guards the consistency check only against itself.
- `bin/sdt:799-805`: `ensure_detached_worktree()` creates a tree but never
  resets it. The Manager (`bin/sdt:1182`, `bin/sdt:1409`) and the Researcher
  (`bin/sdt:1233`, one run per research item, possibly several at once) call
  only that.

**Evidence (run by this audit):**
- A landing that is also the Nth merge, with a red gate: two live runs, `qa`
  and `consistency-check`, both with cwd `qa`, and the tree reset twice.
- A live consistency run plus a new landing: `qa` was reset underneath the
  live run.
- A `manager` worktree created at commit A stayed at A after main moved to B,
  and a file left by the previous run was still present.

**Consequence:**
- A QA bisect checks out other commits under the consistency audit, and the
  next gate run resets the tree mid-audit, so findings are read from the
  wrong commit.
- The Manager triages against stale docs.
- Researchers reproduce on stale code, in a tree an earlier run may have
  dirtied.

**Acceptance criteria:**
- The consistency check has its own persistent detached worktree.
- No persistent worktree is reset while a live run has it as its cwd.
- Manager and Researcher worktrees are reset to the current default-branch tip
  before every run.
- Concurrent runs of one role never share a tree: one tree per concurrent
  run, e.g. `researcher-<slug>`.
- `docs/team-charter.md#branch-and-worktree-naming` lists every persistent
  role worktree the orchestrator uses.
- `tests/test_units.py` proves:
  - with a live QA run, `run_consistency()` uses a different tree;
  - a gate run while a consistency run is live does not reset the
    consistency tree;
  - a Manager run after the tip moves starts in a tree at the new tip.

**Exact files to change:** `bin/sdt` (`run_consistency`, `run_qa_gate`,
`intake`, `ask_manager`, `apply_triage`), `docs/team-charter.md`,
`tests/test_units.py`.

**Suggested approach:** obtain role worktrees through one helper that resets a
persistent tree before the run and refuses one that a live run in
`self.runs` already uses as its cwd.
