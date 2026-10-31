---
by: qa (consistency-check)
---
# The statusline counts ledger `history` entries as items, so its numbers and its second line are wrong in every run

*Line numbers are at `547befb`.*

**What's wrong:** `statusline.sh` assumes an item object holds only scalars
and the `grouped` array. But the orchestrator writes every item with a
`history` array, and each history entry carries its own `stage` key. So the
script counts history entries as items, and its per-item lookup lands on a
history entry instead of the item.

**Spec (canonical):**
`docs/team-charter.md#progress-ledger--the-runs-machine-readable-state`:
- Lines 314-317: the schema is "the **single contract** every consumer reads
  (… any status line …); a consumer never redefines it".
- Lines 346-352: an item carries optional `checks: [{…}]` and
  `history: [{ at, stage, text }]`, both arrays of objects.

**Contradicting side:**
- `extras/claude/skills/statusline/statusline.sh:91-92` redefines the schema:
  "Item objects contain only scalars and the `grouped` array, so `{[^{}]*}`
  isolates each one".
- `statusline.sh:141`: `total` counts every `stage:` key in the file.
  `count_stage` (lines 85-88) counts every match of one stage value the same
  way.
- `item_obj` (lines 93-96) returns the first innermost `{…}` whose `stage`
  matches. That is a history entry, with no `slug`, `priority`, `agent` or
  `model`.
- The writer: `bin/sdt:1118` puts `"history": it.history[-12:]` into every
  item row, and `Item.enter()` (`bin/sdt:1042-1045`) appends
  `{"at", "stage", "text"}` on every transition. `checks` rows
  (`bin/sdt:1126-1127`) are nested objects too.

**Evidence (run by this audit):** the script at `5c1e96c` read the live
ledger of the running `dogfood-2` run (`.delivery-team/progress/state.json`,
written 2 s earlier). That ledger held 11 items (4 done, 4 review, 2 queued,
1 implementing) carrying 57 history entries. The script printed:

```
⛭ team 8/68 ▕█▓▓▓▓▓▓░░░▏ impl:16 review:18 land:7 blocked:0 · tip 5c1e96c ↑4 · 43m
  ⛭ review — (— · — · — · —)
```

**Consequence:**
- Every Claude Code user with the statusline installed sees wrong totals and
  wrong stage counts, including a `land:` count when nothing is landing.
- The review/blocked detail line never names an item.
- The error grows with each item's history (up to 12 entries per item).

**Acceptance criteria:**
- Counts and the detail line come only from each item's own top-level fields,
  whatever optional nested arrays the item carries (`history`, `checks`,
  `dependsOn`, `grouped`).
- The script stays pure POSIX shell, with no jq.
- The comment at `statusline.sh:91-92` describes the charter's schema, or is
  removed.
- A test in `tests/` runs `statusline.sh` on a ledger produced by
  `Orchestrator.write_ledger()`, with items whose history spans several
  stages. It asserts the done/total figure, each stage count, and the slug on
  the detail line. This puts the script under the gate.

**Exact files to change:**
- `extras/claude/skills/statusline/statusline.sh`.
- `tests/test_units.py`, or a new `tests/test_statusline.py`.

**Suggested approach:** before scanning, cut each item's nested arrays out of
the flattened JSON, or split the `items` array by brace depth. The cut must
work on both `state.json` (`indent=1`) and the `state.js` wrapper. Keep the
script's degrade-to-silence behaviour.
