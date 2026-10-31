---
by: qa (consistency-check)
---
# A research-retired item is marked `done`, so the board counts it as landed

*Line numbers are at `acc20ec`.*

**What's wrong:** when research retires an item (`FILED` or `NO-ITEM`), the
orchestrator moves the item to the ledger stage `done`. That is the stage a
merged item gets. The board counts every `done` row under "Landed", so a
dissolved or superseded item shows as landed. `DRAINED` counts only real
merges, so the two reports disagree.

**Spec (canonical):**
- `docs/team-charter.md#backlog-conventions` (line 407): "An item is **done
  when the merging commit deletes its item file** — nothing else marks it
  complete."
- `docs/team-charter.md#progress-ledger--the-runs-machine-readable-state`
  (lines 392-395): the `stage` enum "is what a board groups into lifecycle
  columns and what a status line aggregates into counts".
- `skills/team/SKILL.md:98-100` restates the rule: "an item is done when the
  landing commit deletes its item file".

**Code (the delta):**
- `bin/sdt:1994` (`on_researcher`, inside `apply()`): after
  `retire_items`, `it.enter("done", f"retired by research ({message})")`.
  No merging commit was made. The retirement is a housekeeping deletion
  (`bin/sdt:964-970`).
- `bin/sdt:2058-2066`: `DRAINED` reports `"landed": self.merges`. 67563a6
  made that change so that retired items would not count as landed.
- `assets/dashboard.html:610`: `done = by.done.length`. Lines 366-367 render
  it under the label "Landed … of N items". Line 648 turns the status into
  "Drained — all N items landed" once every row is `done`.
- `extras/claude/skills/statusline/statusline.sh:142` counts `done` rows into
  the progress bar.

**Verified:** in a scratch copy of `acc20ec`, a stub run over
`P2-research-dissolves` and `P2-plain` drained with
`{"landed": 1, "blocked": []}`. Its `state.json` held both items at stage
`done`: `P2-plain` (merged) and `P2-research-dissolves`, noted "researched;
no item: …". The board code then renders "Landed 2 of 2 items". The page
itself was not opened in a browser.

**Consequence:** the owner's board and statusline overstate what landed. An
item research dissolved, or replaced with other items, reads as delivered
work, and the board says "all items landed" while `DRAINED` says fewer.

**Acceptance criteria:**
- A research-retired item never appears in the ledger with stage `done`.
  Only an item whose merging commit deleted its file is `done`.
- `tests/test_e2e.py::test_research_failure_blocks_and_no_item_retires` (or a
  sibling) reads `state.json` after the run. It asserts that the number of
  `done` items equals `DRAINED`'s `landed`, and that `P2-research-dissolves`
  has no `done` row.
- A retired item does not hold the run open: `drained()` still returns once
  nothing else is in flight. A regression item that research retires still
  counts as closed in `regression_open`, so the next red with the same
  failures reaches QA again.

**Exact files to change:** `bin/sdt` (`on_researcher`, and `write_ledger` or
`Item` if a flag is used), `tests/test_e2e.py`.

**Suggested approach:** keep the retired `Item` in memory, with a `retired`
flag that `drained()` and `regression_open` treat as closed, and leave it out
of the ledger's `items`. The `research` event already records the
retirement. Simply deleting the item from `self.items` is the wrong way:
`regression_open` (`bin/sdt:1863-1871`) treats a missing item as still open.
The stage enum is fixed by the charter, so do not add a `retired` stage
without an owner decision.
