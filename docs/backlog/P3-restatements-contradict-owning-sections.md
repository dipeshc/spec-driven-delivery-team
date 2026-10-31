---
by: qa (consistency-check)
---
# Nine restatements contradict the section that owns the rule

**What's wrong:** in nine places a doc restates a rule differently from the
section that owns it. Each entry gives the canonical side, the contradicting
text and the edit. All nine are doc-only edits; where code is involved, it
already follows the canonical side.

1. **Stall limit**
   - Canonical: `docs/team-charter.md#role-runs--how-every-role-executes`
     (lines 119-122) judges stalls by log growth only "on an engine whose
     adapter streams events (`streams = true`) … an engine that is silent
     until it finishes is judged by the budget alone" (`bin/sdt:579`).
   - Contradicting: `docs/config.template.toml:68` "A run whose output has not
     grown for this long is treated as dead."
   - Edit: add "on an engine whose adapter streams events (`streams = true`)".
2. **Adopt exhaustion**
   - Canonical: charter lines 123-124, "bounded by `adopt_attempts`, after
     which triage decides" (`bin/sdt:1429-1435`).
   - Contradicting: `docs/config.template.toml:70` "Times a dead developer run
     is re-dispatched with adopt before the item blocks."
   - Edit: "… before triage decides its fate."
3. **Who runs the full gate**
   - Canonical: charter line 586, "the orchestrator runs the gate itself on
     every landed tip", and `docs/architecture.md:41`.
   - Contradicting: `docs/config.template.toml:23-24` "Full gate: what QA runs
     on every new default-branch tip."
   - Edit: "what the orchestrator runs on every new default-branch tip (QA
     root-causes a new failure)".
4. **Manager call points**
   - Canonical: charter line 576 lists the `DECISION-REQUEST` events
     `BLOCKED`, `DEVELOPER-FAILED`, `REVIEW-ROUNDS-EXCEEDED`, `MERGE-BLOCKED`,
     `MERGE-CLERK-FAILED`, `UNEXPECTED-PAYLOAD` and `UNEXPECTED-VERDICT`.
   - Contradicting: `docs/architecture.md:37` "called by the orchestrator at
     four points: intake, a BLOCKED developer, an exhausted review loop, a
     blocked landing".
   - Edit: name intake plus the decision events, or point at the charter's
     message table.
5. **Team roles and the frontier tier**
   - Canonical: charter lines 3-5 and 112-114, and
     `docs/architecture.md:75-78`. The team includes the Researcher and the
     consistency check, both on the frontier tier.
   - Contradicting: `README.md:32` "Five roles, each deliberately narrow" (the
     table lists five), and `README.md:112-113` "a frontier-tier model for the
     judgment roles (Manager, Reviewer, Merge-Clerk, QA)".
   - Edit: count and name the Researcher and the consistency check, and
     complete the frontier list.
6. **The main tree after a landing**
   - Canonical: charter lines 255-260 perform the merge "with the owner's own
     uncommitted edits untouched". `bin/sdt:937-940` reports a status change
     without cleaning anything.
   - Contradicting: `roles/merge-clerk.md:36-38` "the orchestrator
     fast-forwards it to the sha you report … and asserts it is clean
     afterwards."
   - Edit: "… and leaves the owner's uncommitted edits untouched".
7. **Whether spikes run the quality gate**
   - Canonical: `roles/exploration.md`, Method step 4 (lines 93-100): "the
     quality gate must pass for what you touched … A spike that reddens the
     suite is not done."
   - Contradicting: `skills/team/exploration-and-promotion.md:30` "Spikes skip
     the quality gate on the way out and pay it back at promotion", and
     `roles/exploration.md:131-132` "the spike pays back the quality gate it
     skipped".
   - Edit both: a spike skips the review pipeline (independent review, the
     Merge-Clerk, the full gate on a landed tip), not the gate for what it
     touched.
8. **What the scoped-writers list covers**
   - Canonical: the charter's message table at line 587 ("the orchestrator
     appends the patterns to the known-failures file") and line 595
     (ui-inspector `items[{filename, body}]` filed by the orchestrator), and
     `roles/researcher.md:69-70` ("retires the originating item").
   - Contradicting: `docs/team-charter.md#scoped-writers-to-the-main-working-tree`
     item 3 (lines 272-280). Its explicit-path list ("backlog item files
     returned by the QA, Researcher or consistency check …; moving an item to
     `blocked/` …; worktree and branch lifecycle; and the progress ledger")
     leaves out three writes:
     - the known-failures append and commit (`bin/sdt:968-980`);
     - deleting a researched item (`bin/sdt:1742-1757`);
     - items filed from any role's `sdt role --file-items` run
       (`bin/sdt:2087-2089`).
   - Edit: add those three writes to item 3.
9. **"The engine never sees the main working tree"**
   - Canonical: charter lines 96-100. The run context names "the repository
     root, … the paths of this charter and the profile, the backlog and
     worktree locations", and every role is told to read
     `<repo>/.delivery-team/profile.md` (e.g. `roles/manager.md:23`).
   - Contradicting: `docs/team-charter.md#engines--any-coding-cli-through-an-adapter`
     (lines 154-155) "and the engine never sees the main working tree."
   - Edit: "the main working tree is never a granted directory: a run reads
     what its context points at there and never writes it."

**Consequence:** consumers and roles read each contradicting sentence as
true. For example, a project that tunes `stall_seconds` for a non-streaming
engine expects kills that never come.

**Acceptance criteria:**
- Each of the nine edits is made, and nothing else changes.
- `git grep` finds none of the quoted contradicting phrases.
- There is no test surface: prose is verified by the reviewer's reading
  (profile, Quality gate → Not covered).

**Exact files to change:** `docs/config.template.toml`,
`docs/architecture.md`, `README.md`, `roles/merge-clerk.md`,
`roles/exploration.md`, `skills/team/exploration-and-promotion.md`,
`docs/team-charter.md`.

**Suggested approach:** one docs-only commit, which the Reviewer's docs-only
carve-out covers.
