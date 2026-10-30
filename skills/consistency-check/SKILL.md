---
name: consistency-check
description: >
  Two-phase specification audit for a docs-as-spec project: phase 1 makes sure
  the spec agrees with ITSELF (contradictions, terminology drift, broken
  links/anchors, decision-record coherence, residue of earlier versions),
  phase 2 measures the CODE against the spec (docs are truth; every confirmed
  delta is a code bug). All findings
  are FILED as backlog item files — nothing is fixed in place. Run it whenever
  a docs-vs-docs or docs-vs-code audit is wanted: on request from the owner or
  the root instance, ad hoc against a recent change, or by the QA agent on its
  green-heartbeat cadence. Requires a frontier model. Applicability depends on
  the project profile's "Specification source of truth" section.
---

Run the two-phase consistency audit. **You file findings; you fix nothing** —
not even a broken link. Every finding becomes a backlog item that a Developer
lands through review, because under the team model every doc change goes
through a Reviewer and the Merge-Clerk like any other change.

This file owns the method. `/delivery-team:consistency-sweep` runs the same
method as a whole-spec sweep — a class per agent in parallel, every finding put
to a skeptic before it is filed — and is the better choice when the scope is
everything rather than a range. Follow this skill for the audit itself either
way.

## Before anything: applicability gate

Read `<repo>/.delivery-team/profile.md`, section **Specification source of
truth**, and `${CLAUDE_PLUGIN_ROOT}/docs/team-charter.md`.

- **Docs are spec: yes** → run this skill as written, scoped to the profile's
  docs root.
- **Docs are spec: no** → phase 2 does not apply in this direction; the code is
  the truth and the docs follow it. Degrade to phase 1 only, and re-frame it:
  documentation that contradicts *itself* is still a real defect worth filing,
  but a doc-vs-code mismatch is a **stale doc**, not a code bug — file it as a
  documentation-update item and never as a behaviour change.
- **Docs root: `n/a`** (no documentation tree to audit) → this skill does not
  apply. Say so and file nothing; do not invent a spec surface.

Only audit the doc kinds the profile actually declares. If **Decision records**
is `n/a`, skip the decision-record checks entirely rather than inventing an ADR
convention. If the project has no glossary, skip the terminology check rather
than nominating canonical terms yourself.

**Capability gate:** this audit demands frontier judgment — per the charter's
capability gate, if you are not on a frontier model, stop and say so; file
nothing.

## Incrementality

Keep an audit marker (last-audited default-branch SHA + date) in your agent
memory. Scope each pass to `git log <marker>..<default-branch>` — the docs and
code that actually changed — plus any doc a changed doc references. A first run
(no marker) sweeps everything. Update the marker only after the pass completes.

Carry forward inherited invariants and previously dismissed judgment calls from
your audit memory, and honour the profile's **Project-specific content rules** —
a convention that was deliberately chosen (or deliberately removed) is not a
finding. Check that memory — and the docs and history — before flagging
anything that looks like a long-standing, uniform pattern; a uniform
"violation" across an entire docs tree is far more likely to be the project's
convention than a defect.

## Phase 1 — spec vs spec (the docs agree with themselves)

Read the actual doc text for every candidate finding — no grep-only
conclusions. Hunt, in descending value order:

1. **Cross-document contradictions** — the same fact asserted two ways (default
   values, capability/permission matrices repeated across documents, status
   codes and route shapes, config field names, enum lists repeated across docs).
2. **Terminology drift** from the project's glossary, where one exists — the
   glossary is canonical for the terms it defines.
3. **Reference integrity** — every relative link resolves; every `#anchor` has
   a generating heading (GitHub slug rules, so a heading containing ` — ` yields
   a double hyphen); every path built from a plugin-root or similar token exists;
   every citation of a section title matches that heading verbatim; every
   decision-record citation points at a real record; and every behaviour a file
   cites is actually described where it says it is.
4. **Decision-record coherence** (where the profile declares them) — numbering
   without gaps/duplicates; superseded decisions marked and pointing forward; no
   two live records deciding one question opposite ways; no informal decision
   log contradicting a numbered record without a dated correction.
5. **Intra-document self-contradiction.**
6. **Residue of earlier versions** (charter: "Spec prose is timeless") —
   historical narration or incident stories in place of present-tense
   rationale; sections, fields, or files nothing consumes; the same rule
   legislated in two places where one should own it and the other point at it;
   metadata (manifests, frontmatter, descriptions) that no longer matches what
   it describes; `DELETE WHEN` tags whose trigger has fired. (On uniform,
   long-standing patterns, the Incrementality caution above applies.)

**Resolving a contradiction on paper before filing:** pick the canonical side
from the spec's own evidence — the glossary for terminology; a newer decision
record over an older; explicitly-normative over passing mention; the owning
section over an incidental restatement; an owner ruling over anything that
predates it. The item you file states the canonical side, quotes both locations,
and lists the exact edits needed. **Genuinely undecidable** (a real product
choice with no anchor to break the tie) → file into the backlog's `blocked/`
subdirectory quoting both sides and phrasing the open question — the call is the
owner's, never yours.

## Phase 2 — spec vs code (the code obeys the now-mapped spec)

*Only when the profile says docs are spec.*

Docs are the truth: every confirmed delta is a bug **in the code** — unless it
sits on a contradiction phase 1 just filed, in which case reference that item
instead of double-filing.

- Work from the spec inward: for each changed-in-range doc claim (routes,
  defaults, permission gates, invariants, wire shapes), find the implementing
  code and verify the claim with `file:line` evidence. Then sweep the changed
  code the other way: behaviour with no governing spec = an adjudication
  candidate for `blocked/`, not a silent pass.
- **Confirmed deltas only.** A delta you could not verify in the code is not
  filed — noted as unverified in your report at most. Run the relevant test or
  read the actual runtime path before claiming divergence. Never claim a
  verification you did not run.

## Filing

- One item file per real defect, in the location and under the conventions named
  in the profile's **Backlog** section, priority encoded in the filename: the
  top correctness priority for a spec-forbidden behaviour running in code, lower
  priorities by user impact. Frontmatter `by: qa (consistency-check)`. Body: the
  claim, both sides quoted (doc `path#section` vs code `file:line`), the
  canonical resolution, and what the fix must change.
- **Batch pure mechanical rot** (dead links, drifted terms, typo'd references)
  into ONE low-priority `doc-rot-<date>` item listing every instance — dozens of
  one-line items help nobody.
- Commit explicit-path (`docs(backlog): qa consistency audit — …`, or the
  project's equivalent scope; `git add <path>`, never `git add -A`).
- Then report: scope audited (range), items filed with priorities, anything left
  unverified, marker updated.
