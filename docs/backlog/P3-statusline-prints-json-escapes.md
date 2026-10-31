---
by: qa (consistency-check)
---
# The statusline prints ledger strings with their JSON escapes, and cuts a note off at its first quote

*Line numbers are at `c95ed21`.*

**What's wrong:** `statusline.sh` reads each string field by matching
`"[^"]*"` and prints the match as is, without decoding JSON escapes. The
orchestrator writes the ledger with `json.dumps`, which escapes every
non-ASCII character. So the statusline shows:
- `\u00d7` in place of every grouped item's `×`;
- `\u2014` in place of the `—` placeholder, and of any dash in a note.

A note that contains a quote is cut off at the backslash.

**Spec (canonical):**
- `docs/team-charter.md#progress-ledger--the-runs-machine-readable-state`:
  - lines 323-325: the `state.json` twin carries "the same object", and
    `state.js` is "that JSON wrapped mechanically";
  - lines 327-330: the schema is "the **single contract** every consumer
    reads (the shipped `dashboard.html`, any status line, any future
    renderer); a consumer never redefines it";
  - line 343: `priority` is the "filename priority, or a grouped label e.g.
    "P0 ×2 + P1"";
  - lines 345-346: `agent` and `model` belong to the assigned run, `or "—"`;
  - line 351: `note` is a "short reason, chiefly for blocked".
- `extras/claude/skills/statusline/SKILL.md:18-20`: line two is "the item in
  review and/or blocked, with its agent, model, and stage-elapsed".

**Code (the defect):**
- `bin/sdt:1180` (`write_ledger`): `json.dumps(state, indent=1)`. With the
  default `ensure_ascii=True`, it writes `×` as `\u00d7`, `—` as `\u2014`,
  and a `"` inside a string as `\"`.
- `extras/claude/skills/statusline/statusline.sh:140-143` (`ofield`) and
  `:81-84` (`str_of`) capture `\([^\"]*\)` and print it unchanged. The
  capture stops at the first `"`, even an escaped one.
- The affected fields:
  - `slug` and `priority` (line 224);
  - `agent` and `model` (lines 225 and 232);
  - `note` (line 233);
  - the run `label` (line 171).
- `bin/sdt:1592` (`block`) sets `note` to the block reason. That reason is
  free text: either the Manager's, or the engine's own error line (charter
  lines 109-111). A dash or a quote in it is common.

**Evidence (run by this audit):**
- The live ledger, `.delivery-team/progress/state.json` (written by the
  running orchestrator), renders line two as
  `⛭ review P3-direct-lane-full-gate-when-no-run-is-active (P3 \u00d72 · reviewer-1 · opus · 5m 30s)`.
  When read, that file held ten `\u` escapes:
  - seven in grouped priorities;
  - one in each of an item's `agent` and `model`, both `\u2014`;
  - one in an item's `detail`.
- A scratch ledger, written with `json.dumps(indent=1)` as `write_ledger`
  does, held one blocked item whose note was
  `engine error — the "model" flag was refused`. The script at `c95ed21`
  printed `⛭ blocked P2-a (engine error \u2014 the \ · developer · m · 5s)`.

**Consequence:**
- Every grouped item in review shows `P3 \u00d72` on the owner's always-on
  statusline.
- A blocked item that was never dispatched shows `\u2014 · \u2014` for its
  agent and model.
- A blocked item's reason is the one thing the owner needs from that line.
  It is garbled at its first dash and truncated at its first quote.
- The board page decodes the same file correctly, so the two views disagree.

**Acceptance criteria:**
- The statusline prints `×`, `—` and a quoted phrase in any ledger string
  exactly as the orchestrator holds them. This holds for both the
  `state.json` and the `state.js` form.
- A test in `tests/test_units.py` covers this. Extending
  `test_counts_and_detail_come_from_items_not_their_history` is one way.
  - Its ledger is written by `Orchestrator.write_ledger()`. It has a grouped
    item in review, and a blocked item whose note holds `—` and a `"`.
  - It asserts that line two contains the grouped label (for example
    `P2 ×2`) and the whole note.
  - It fails against the script at `c95ed21`.
- `sdt status` still prints the ledger.
- The reviewer opens the board on a ledger with those strings and checks
  that it renders them, because the gate does not exercise the page
  (profile, Quality gate → Not covered).

**Exact files to change:**
- `bin/sdt`: `write_ledger`, plus the encoding of the ledger write and of
  `cmd_status`'s read (`bin/sdt:2291`).
- `extras/claude/skills/statusline/statusline.sh`: `ofield` and `str_of`.
- `tests/test_units.py`.

**Suggested approach:**
- Write the ledger with `ensure_ascii=False`, and read and write it as UTF-8
  explicitly. Then the only escapes left in a string are `\"`, `\\` and
  control characters.
- Make the script's string capture escape-aware, then unescape `\"` and
  `\\`. Keep it POSIX: BSD sed has no `\|`. An awk scan like the item walk's
  string loop is one option.
- Decoding `\uXXXX` in the shell is the alternative, but it is harder to keep
  portable.
- The page declares `<meta charset="utf-8">` (`assets/dashboard.html:4`) and
  loads `state.js` through a script tag. A UTF-8 file should therefore need
  no page change. Confirm that by opening the page.
