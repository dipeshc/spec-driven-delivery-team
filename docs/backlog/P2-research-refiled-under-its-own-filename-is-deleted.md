---
by: qa (consistency-check)
---
# A researched item filed under the originating item's own filename is deleted by the retirement

*Line numbers are at `40f24be`.*

**What's wrong:** when the Researcher returns `FILED` with an item whose
filename is the originating item's own, the orchestrator writes and commits
that item, then retires the originating path. That deletes the item it has
just filed. Even if the file survived, its slug stays known, so the run
would never triage it.

**Spec (canonical):**
- `roles/researcher.md#what-you-return` (lines 68-70): "The orchestrator
  writes and commits the files and retires the originating item either way".
- `docs/team-charter.md#scoped-writers-to-the-main-working-tree`, writer 3
  (lines 290-294): the orchestrator's housekeeping writes "backlog item files
  returned by the QA, Researcher or consistency check as `{filename, body}`
  pairs" and does the "deleting a researched item".
- `roles/researcher.md:15`: the Researcher exists to "hand back an item a
  capable-but-cheaper developer can action cold". The filed item is the run's
  output. Retiring the rough ask must not destroy it.

**Code (the delta):**
- `bin/sdt:2001` (`on_researcher`, `apply()`): `self.p.file_items(items, …)`
  writes `<backlog>/<filename>` and commits it (`bin/sdt:948-964`).
- `bin/sdt:2009`: `self.p.retire_items([self.p.root / rel for rel in it.paths], …)`
  runs `git rm` on every originating path that is a file
  (`bin/sdt:975-981`). When a filed name equals an originating path, that
  file is the one just written.
- `bin/sdt:2010`: `it.retired = True`. A retired item keeps stage `blocked`
  with `parked` false, so `retriageable()` (`bin/sdt:1092-1094`) is false and
  the slug stays in `known` (`bin/sdt:1285`). Every later intake in the run
  would skip a file with that name.
- Neither the role nor the charter forbids reusing the name, and the role's
  example names `P2-<short-slug>.md` (`roles/researcher.md:56`). A rough ask
  filed as `P2-foo.md` and sharpened into a full item is naturally named
  `P2-foo.md` again.
- The stub never reaches this case: its Researcher files
  `P2-researched-<slug>.md` (`tests/fake_engine.py:128`).

**Verified (run by this audit):** in a scratch copy of `40f24be`, a unit test
built on `triage_orchestrator` (tests/test_units.py) triaged `P2-rough-ask` to
research. It then fed `on_researcher` a `FILED` result holding
`{"filename": "P2-rough-ask.md", "body": "# Sharpened …"}` and flushed
housekeeping. Results:
- The log read `chore(backlog): file 1 item(s) — research for P2-rough-ask`,
  then `chore(backlog): retire P2-rough-ask — superseded by researched
  item(s)`, with body "Filed: P2-rough-ask.md".
- Afterwards `docs/backlog/P2-rough-ask.md` did not exist and
  `scan_backlog()` returned nothing.
- `known` still held `P2-rough-ask`.
- The `research` event read "P2-rough-ask: FILED; researched; filed
  P2-rough-ask.md".

**Consequence:** the item the research run produced leaves the backlog
without a word, while the event and the commit body say it was filed. It
survives only in git history, and nothing tells anyone to recover it.

**Acceptance criteria:**
- After `FILED` with an item whose filename equals an originating item's
  path, that file exists with the researched body, and no commit deletes it.
- The retire commit deletes only originating paths that no filed item
  rewrote. When every originating path was rewritten, no retire commit is
  made.
- The same run triages the rewritten item afresh: the next intake's
  `TRIAGE-REQUEST` lists its slug with the researched text.
- An originating item whose path was not reused is retired as it is today.
  `test_research_retired_regression_is_closed_but_never_done` and
  `test_research_failure_blocks_and_no_item_retires` still pass.
- A new unit test in `tests/test_units.py` covers the same-filename case and
  fails against `40f24be`.

**Exact files to change:** `bin/sdt` (`on_researcher`), `tests/test_units.py`.

**Suggested approach:** in `apply()`, collect the paths `file_items` wrote,
and pass `retire_items` only the originating paths not among them. When an
originating file was rewritten, drop its `Item` from `self.items` instead of
marking it retired, so the next intake sees the slug as fresh. A regression
item rewritten in place then stays open in `regression_open`. That is right,
because its file still exists. Keep the commit body honest: name a rewritten
file as rewritten in place, not as retired.
