---
by: qa (consistency-check)
---
# A `NO-ITEM` research result leaves the originating item in the backlog, shown as blocked

**What's wrong:** the orchestrator retires the originating item only when
research returns `FILED`. On `NO-ITEM`, the item file stays in the backlog
root while the run reports the item as `blocked`. The next `sdt run` triages
it and sends it to research again.

**Spec (canonical):** `roles/researcher.md#what-you-return` (lines 62-70):
`NO-ITEM` is for "when the question dissolves on inspection (already true, not
reproducible, not worth doing)", and "The orchestrator writes and commits the
files and retires the originating item".

**Code (the defect):**
- `bin/sdt:1742-1759`: `apply()` deletes the originating file only
  `if it is not None and message == "FILED"`. For `NO-ITEM` it files nothing,
  deletes nothing, and records neither the `finding` nor the `why`.
- The item keeps the in-memory stage `blocked` set at `bin/sdt:1220`.
  `run()` (`bin/sdt:1819-1833`) therefore lists it under `blocked` in
  `DRAINED`, although no file is in `blocked/`.

**Consequence:** an item that research has already dissolved costs a frontier
Researcher run on every later `sdt run`. The `DRAINED` summary sends the owner
to `blocked/` for an item that is not there.

**Acceptance criteria:**
- On `NO-ITEM`, the orchestrator deletes the originating item file(s) in one
  explicit-path commit whose message carries the researcher's `finding` and
  `why`.
- The item is no longer reported as blocked.
- `tests/fake_engine.py` lets a marked slug return `NO-ITEM`, and
  `tests/test_e2e.py` asserts:
  - the file is gone;
  - the item is not in `DRAINED`'s `blocked` list;
  - the commit carries the finding.

**Exact files to change:** `bin/sdt` (`on_researcher`), `tests/fake_engine.py`,
`tests/test_e2e.py`.

**Suggested approach:** one retirement helper used by both `FILED` and
`NO-ITEM`; only the commit subject and the list of filed items differ.
