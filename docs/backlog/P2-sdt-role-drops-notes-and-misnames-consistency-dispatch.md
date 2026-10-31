---
by: qa (consistency-check)
---
# `sdt role` drops `notes_for_next_run`, and its consistency-check dispatch is not in the charter

**What's wrong:**
- An on-demand role run (`sdt role <name>`) never appends the run's
  `notes_for_next_run` to the role's notes file. For the consistency check,
  this means the audit marker is never kept, so every on-demand pass is a full
  first sweep.
- The on-demand consistency dispatch is `CONSISTENCY-CHECK-REQUEST` with no
  `tip`, a message the charter's table does not define.
- The consistency-check skill offers a narrowing payload that the charter
  rules out.

**Spec (canonical):**
- `docs/team-charter.md#role-runs--how-every-role-executes` (lines 129-132):
  "Each role has a notes file … a run may return `notes_for_next_run` to
  append to it."
- `docs/team-charter.md#message-schemas--the-canonical-payload-table`
  (line 588): "Orchestrator → consistency check | `RUN-CONSISTENCY` | `{tip}`
  (trigger only; the pass's scope and audit range are the role's own)".
- `roles/consistency-check.md` (lines 22-23, 47-52): "Your dispatch is
  `RUN-CONSISTENCY {tip}`". The marker lives in the notes file, and the new
  marker is returned in `notes_for_next_run`.

**Contradicting side:**
- `bin/sdt:2062-2091`: `cmd_role()` has no `append_notes` call (compare
  `on_run_done`, `bin/sdt:1355-1356`).
- `bin/sdt:2074` defaults the message to `f"{args.name.upper()}-REQUEST"`,
  which gives `CONSISTENCY-CHECK-REQUEST` with no `tip`.
- `skills/consistency-check/SKILL.md` (lines 23-28): "Optionally narrow the
  pass with a payload, which the role treats as its audit range: …
  `{"range": "<sha>..<default-branch>", "focus": "docs/architecture.md"}`".
  Lines 30-32 promise that "each pass is incremental".
- Observed directly: this audit was itself dispatched by `sdt role
  consistency-check --file-items`, with payload
  `{"message": "CONSISTENCY-CHECK-REQUEST"}` and notes "(none)".

**Canonical resolution:** the charter.
- `sdt role` keeps notes like any other run.
- The consistency check is always dispatched as `RUN-CONSISTENCY {tip}`.
- The skill drops the narrowing-payload paragraph, because the role owns
  scope and range. Its incrementality sentence becomes true once notes
  persist.

**Consequence:** every on-demand audit re-sweeps the whole spec at frontier
cost. The exploration and ui-inspector roles, which run only through
`sdt role`, never get notes either.

**Acceptance criteria:**
- `cmd_role()` appends a successful run's `notes_for_next_run` to
  `.delivery-team/notes/<role>.md`.
- `sdt role consistency-check` sends
  `{"message": "RUN-CONSISTENCY", "tip": <default-branch sha>}` unless the
  caller supplies a payload.
- `skills/consistency-check/SKILL.md` no longer documents a `range` / `focus`
  payload.
- `tests/test_e2e.py` runs `sdt role consistency-check --file-items` on the
  stub, with `tests/fake_engine.py` returning `notes_for_next_run` and echoing
  the message it received. It asserts the notes file holds the note and the
  dispatch was `RUN-CONSISTENCY` with a `tip`.

**Exact files to change:** `bin/sdt` (`cmd_role`),
`skills/consistency-check/SKILL.md`, `tests/fake_engine.py`,
`tests/test_e2e.py`.

**Suggested approach:** reuse `Project.append_notes`. Add a small map of
per-role default payloads in `cmd_role()` (`consistency-check` →
`RUN-CONSISTENCY {tip}`), falling back to the current `<NAME>-REQUEST` rule.
