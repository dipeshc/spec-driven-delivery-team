---
by: qa (consistency-check)
---
# Held items dispatch at once, and a known item is never triaged again

**What's wrong:** a Manager `hold` decision has no effect: the held item is
dispatched on the same tick. The orchestrator also never triages a slug it
already knows. So a held item is never re-asked, and an item the owner moves
back out of `blocked/` during a run is never picked up.

**Spec (canonical):**
- `roles/manager.md#triage-request--new-items-reached-the-backlog`
  (lines 69-72): "**`hold`** — actionable but not yet: it conflicts with
  in-flight work (same files, a dependency, or both needing the same exclusive
  resource). Name what it waits on in `reason`; the orchestrator asks you
  again when the backlog changes."
- `skills/team/SKILL.md#blocks-only-the-owner-can-clear` (lines 137-139):
  "When the condition is repaired, move the item file back out of `blocked/`
  (commit it explicit-path); the orchestrator re-triages it".

**Code (the defect):**
- `bin/sdt:1199-1211` builds every triaged `Item` with
  `note=str(d.get("reason", ""))`. `bin/sdt:1242-1244` handles `hold` only
  with `item.enter("queued", "held: " + reason)`, which writes history text,
  not `note`.
- `bin/sdt:1276-1279`: `dispatch_ready()` skips an item only when
  `it.note.startswith("held")`. The Manager's reason (e.g. "waits on P1-a")
  never starts with that word, so the item is dispatched.
- `bin/sdt:1163-1165`: `intake()` triages only slugs not already in
  `self.items`. Held and blocked items are in it, so they are never
  re-triaged.

**Evidence (run by this audit):**
- Scratch repo with `P1-a` (dispatch) and `P2-b` (`hold`, reason "waits on
  P1-a (same files)"): `apply_triage()` then `dispatch_ready()` dispatched
  `['P1-a', 'P2-b']`.
- An item blocked at triage, then moved back from `blocked/` with `git mv`
  and committed: the next `tick()` started no Manager run, and the item
  stayed `blocked`.

**Consequence:** the Manager's ordering of conflicting work is silently
ignored. Items it held run in parallel with the work they conflict with,
causing rebase churn and burned review rounds. In a `--watch` run, the
owner's documented way to clear a block does nothing until the orchestrator
restarts.

**Acceptance criteria:**
- A `hold` decision is recorded in its own field, not inferred from `note`
  text, and `dispatch_ready()` never dispatches a held item.
- When `backlog_sha` moves, the next `TRIAGE-REQUEST` sends held items back to
  the Manager together with any fresh items.
- An item whose file reappears in the backlog root after being blocked is
  treated as fresh.
- `tests/test_e2e.py`: a stub Manager answers `hold` for a marked slug until
  the item it waits on lands. The test proves the held item is not dispatched
  while held and lands afterwards.
- A unit or e2e test proves an item moved back out of `blocked/` mid-run is
  re-triaged.
- `tests/fake_engine.py` gains the `hold` behaviour those tests need.

**Exact files to change:** `bin/sdt` (`Item`, `intake`, `apply_triage`,
`dispatch_ready`), `tests/fake_engine.py`, `tests/test_e2e.py`.

**Suggested approach:** add `held: bool` to `Item`. In `intake()`, also send
every in-memory held item, and every blocked item whose file is back in the
backlog root, then let `apply_triage()` replace those entries.
