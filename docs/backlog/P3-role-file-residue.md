---
by: qa (consistency-check)
---
# Four pieces of role-file residue describe mechanisms the orchestrator does not have

*Line numbers are at `547befb`.*

**What's wrong:** the role files still describe consumers and mechanics left
over from the Manager-driven version of the pipeline. Nothing in the current
orchestrator implements them. The charter's "Spec prose is timeless"
(`docs/team-charter.md:531-541`) names "references to things that no longer
exist" and "sections nothing consumes" as defects. Each entry below gives the
text, why it is residue, and the edit.

1. **Load accounting by the orchestrator.**
   - Text: `roles/developer.md:114-115`, "run it — and say so in your `notes`
     so the orchestrator can account for the load."
   - Why it is residue: the orchestrator only forwards `notes`, as the
     ledger's `detail` (`bin/sdt:1523`) and to the Reviewer
     (`bin/sdt:1552`). Nothing schedules on it. Before `5f30528` the sentence
     read "so the Manager can account for the load".
   - Edit: "say so in your `notes` so the Reviewer knows the full gate
     already ran", or drop the clause.
2. **"The QA's sweep" for flakes.**
   - Text: `roles/reviewer.md:147-150`. A non-reproducing failure is noted
     "in your verdict for the QA's sweep … proving flakes out is the QA's
     job".
   - Why it is residue: QA runs only on a new full-gate failure
     (`docs/team-charter.md:594`, `roles/qa.md:42`). Nothing sweeps, and no
     field of an `APPROVED` verdict reaches QA: `MERGE-REQUEST` carries no
     notes (`bin/sdt:1628-1637`).
   - Edit: note it in the verdict. A failure that reproduces on the landed
     tip reaches QA through the full gate.
3. **"The filer" who writes the inspector's items.**
   - Text: `roles/ui-inspector.md:223-236`, "give the filer everything it
     needs to write an item that meets the charter's item-shape contract".
     The section then lists four fields: what is wrong, repro, evidence,
     likely cause.
   - Why it is residue: the orchestrator writes each returned `body` verbatim
     (`bin/sdt:913-929`), so no filer composes anything. A body with only
     those four fields is filed without the charter's Consequence,
     Acceptance criteria (with tests), Exact files to change and Suggested
     approach (`docs/team-charter.md:406-424`).
   - Edit: the returned `body` is the item, in the charter's full item shape,
     with the four fields as its evidence.
4. **The `access:` frontmatter key.**
   - Text: every role file declares `access: read` or `access: write`:
     consistency-check:13, developer:10, exploration:13, manager:10,
     merge-clerk:12, qa:12, researcher:11, reviewer:12, ui-inspector:13.
   - Why it is residue: `load_role` stores the key (`bin/sdt:355`,
     `bin/sdt:395`), but nothing reads `Role.access`, and no spec document
     defines it. The charter confines every run "the same way", with
     approvals bypassed (`docs/team-charter.md:151-157`). So `access: read`
     on the Merge-Clerk (which cherry-picks) and on the Reviewer (which
     resets its tree) describes a restriction nothing enforces.
   - Edit: remove the key from the nine role files, remove the `Role.access`
     field, and update its use in `tests/test_units.py:189`. Making runs
     genuinely read-only would be a new decision for the charter, and this
     item does not make it.

**Consequence:**
- Roles follow instructions that lead nowhere: notes nobody schedules on,
  flake reports nobody reads.
- The UI inspector returns items that cannot be actioned cold.
- Readers assume a read-only confinement that does not exist.

**Acceptance criteria:**
- All four edits are made.
- `git grep -n "access:" roles` finds nothing.
- `uv run pytest -q` passes, with `test_prompt_shape` updated for the new
  `Role` signature.
- The prose edits are verified by the reviewer's reading (profile, Quality
  gate → Not covered).

**Exact files to change:**
- `roles/developer.md`, `roles/reviewer.md`, `roles/ui-inspector.md`.
- The frontmatter of all nine `roles/*.md` files.
- `bin/sdt` (`Role`, `load_role`).
- `tests/test_units.py`.

**Suggested approach:** one commit. `item/P2-engine-knowledge-outside-adapters`
(in review) removes the `engines:` line from `roles/ui-inspector.md`'s
frontmatter, two lines below `access:`; rebase onto it.
