---
by: qa (consistency-check)
---
# Owner decision: does the profile's "Sanctioned direct-write paths" scope the orchestrator's housekeeping?

**What's wrong:** the charter and the profile template disagree on what the
profile's "Sanctioned direct-write paths" section covers.

**Evidence (both sides):**
- `docs/team-charter.md#scoped-writers-to-the-main-working-tree`
  (lines 284-287), unchanged since 2026-08-14 (a81b6c8): "The project
  profile's "sanctioned direct-write paths" section names the exact paths for
  that repo: it scopes the housekeeping writes made straight to the main tree,
  not the two merge paths above". The housekeeping writers are item 3 (the
  orchestrator) and item 4 (the owner's session).
- `docs/profile.template.md#sanctioned-direct-write-paths` (lines 100-103),
  added 2026-10-30 (bd1c794): "Paths the owner's session may commit to
  directly on the main working tree … The orchestrator's own housekeeping
  (backlog items, `blocked/` moves, the ledger) is sanctioned by the charter
  and needs no entry."
- This repo's own `.delivery-team/profile.md` follows the charter's reading:
  it lists "`docs/backlog/` — filed items".

**Why it can't be settled on paper:**
- The owning-section rule favours the charter.
- But the charter's sentence predates the orchestrator, which cannot read the
  prose profile.
- The newer template wording matches how the code behaves: `bin/sdt` writes
  the backlog dir and the known-failures file without consulting the profile.

Both readings are coherent.

**Open question for the owner:** which does the profile's list cover?
- **(a) Every housekeeping writer, including the orchestrator.** The template
  drops "needs no entry" and tells consumers to list their backlog dir and
  known-failures file.
- **(b) Only the owner's session's direct writes.** The charter's sentence
  becomes "it scopes the owner's session's housekeeping writes (item 4)".

Recommendation: (b). It matches the implementation and the template's newer
wording.

**Consequence:** consumers fill in the section under different readings. A
role reading it as (a) would report the orchestrator's known-failures commit
as an unsanctioned write.

**Acceptance criteria:** the charter and the template state the same reading,
and this repo's profile entry matches it. There is no test surface (prose).

**Exact files to change:** `docs/team-charter.md` (for b) or
`docs/profile.template.md` and `.delivery-team/profile.md` (for a).

**Suggested approach:** one sentence in whichever file loses.
