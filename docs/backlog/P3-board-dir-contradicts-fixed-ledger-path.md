---
by: qa (consistency-check)
---
# `[board] dir` contradicts the charter's fixed ledger path and breaks the statusline

**What's wrong:** the charter fixes the progress ledger at
`<repo>/.delivery-team/progress/state.js`, but the config template and
`bin/sdt` let a project move it with `[board] dir`. The statusline reads only
the fixed path, so a project that uses the key silently loses its statusline.

**Canonical side:**
- `docs/team-charter.md#progress-ledger--the-runs-machine-readable-state`
  (lines 300-303): the orchestrator "mirrors its pipeline state … to
  `<repo>/.delivery-team/progress/state.js`".
- `#scoped-writers-to-the-main-working-tree` (line 276) gives the same path.
- This is the owning, normative section. Unlike `[worktrees]`
  (`#branch-and-worktree-naming`, lines 440-442), it grants no config
  override.

**Contradicting side:**
- `docs/config.template.toml:89-91`: `[board] dir = ".delivery-team/progress"`.
- `skills/board/SKILL.md:33-34`: "It resolves the board directory from
  `config.toml` (`[board] dir`, …)".
- `bin/sdt:131`, `bin/sdt:213` and `bin/sdt:652`, used by `write_ledger`,
  `cmd_status` and `cmd_board`.
- `extras/claude/skills/statusline/statusline.sh:47` reads
  `"$project_dir/.delivery-team/progress"` whatever the config says.

**Canonical resolution:** the charter. Remove the `dir` key from `[board]`,
and have `bin/sdt` always use `.delivery-team/progress`. Keep `enabled`.

**Consequence:** a project that sets `[board] dir` writes a ledger that the
statusline, and any other consumer that follows the charter, never finds. That
breaks the "single contract every consumer reads" (charter lines 311-313).

**Acceptance criteria:**
- `docs/config.template.toml` has no `[board] dir`, and `bin/sdt` no longer
  reads it.
- `skills/board/SKILL.md` names the fixed path.
- `tests/test_units.py` asserts that `Project.board_dir` is
  `<root>/.delivery-team/progress` even when the config sets `[board] dir`.

**Exact files to change:** `docs/config.template.toml`, `bin/sdt` (`Config`,
`load_config`), `skills/board/SKILL.md`, `tests/test_units.py`.

**Suggested approach:** make the board directory a constant beside
`PROJECT_DIR_NAME`. Optionally, have `sdt doctor` warn when a config still sets
the dropped key.
