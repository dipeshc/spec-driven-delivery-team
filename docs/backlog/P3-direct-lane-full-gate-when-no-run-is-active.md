---
by: qa (consistency-check)
---
# The charter's direct lane names an independent full-gate run that does not exist when no run is active

*Line numbers are at `547befb`.*

**What's wrong:** the charter's direct-lane writer says, with no condition,
that the QA full-gate run on the new tip is the lane's independent
verification. But the orchestrator gates only tips that land while it is
running. It treats the tip it opens on as already accounted for, because "its
own lander" ran the full gate. That rule (a lander with no run active runs
the full gate itself) lives only in the team skill and a code comment. The
owning section does not state it.

**Canonical side:** the owning section,
`docs/team-charter.md#scoped-writers-to-the-main-working-tree`, writer 2
(lines 263-273). It names the three proofs (the scoped gate, every triggered
guard, one self-review pass) and says: "The QA full-gate run on the new tip is
this lane's independent verification; it is not a licence to skip the three."
`roles/qa.md` lines 36-38 restate it: "The full-gate run on every new tip is
the independent verification that lane depends on."

**The other side (where the rule actually lives):**
- `skills/team/SKILL.md:64-66`: "The orchestrator's full-gate run on every
  new tip is the independent verification for this lane when a run is active;
  otherwise run the full gate once before you call it done."
- `bin/sdt:1071-1074` (`Orchestrator.__init__`): "It starts at the tip the
  run opens on: work landed while no run was active had its full gate run by
  its own lander." So the opening tip is never gated.

**Canonical resolution:** sharpen the owning section to match what the skill
and the code already implement. When no run is active, the lander runs the
full gate itself before calling the change done, because no orchestrator
gate will. This states a decision already made; it does not re-decide it.
`roles/qa.md` lines 36-38 then follow with "while a run is active".

Having the orchestrator gate the tip it opens on would be a different
decision and a code change. That is the owner's call, and this item does not
make it.

**Consequence:**
- A reader of the charter, which is the owning text, believes every
  direct-lane tip gets an independent full gate.
- An owner's session that follows the charter alone skips the full gate when
  no run is active. The regression is then first blamed on the next
  team-lane landing.

**Acceptance criteria:**
- Charter writer 2 states the no-run-active case.
- The team skill restates it or points at the charter, rather than
  legislating it separately.
- `roles/qa.md` lines 36-38 say the orchestrator's full-gate run covers tips
  landed while a run is active.
- `git grep` shows the rule stated in one place, with the others pointing at
  it.
- There is no test surface (profile, Quality gate → Not covered). The code
  already behaves this way (`bin/sdt:1074`).

**Exact files to change:** `docs/team-charter.md`, `roles/qa.md`,
`skills/team/SKILL.md`.

**Suggested approach:** one docs-only commit.
