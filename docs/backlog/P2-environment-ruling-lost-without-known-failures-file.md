---
by: qa (consistency-check)
---
# QA's environment ruling is discarded when no known-failures file is configured, so the same red pages QA on every tip

*Line numbers are at `547befb`.*

**What's wrong:** `[qa] known_failures` defaults to empty, both in the shipped
template and in this repo's config. With no file configured, the orchestrator
drops QA's `ENVIRONMENT` patterns, writing only a stdout log line. It also
releases the failure signature. Every later tip that fails the same way then
dispatches another frontier QA run to rule on the same fault again.

**Spec (canonical):**
- `docs/team-charter.md#message-schemas--the-canonical-payload-table`
  (line 595): `ENVIRONMENT` `{patterns[], reason}` "(the orchestrator appends
  the patterns to the known-failures file)". This is unconditional.
- `roles/qa.md#root-cause-then-rule` (lines 62-65): "the orchestrator records
  it in the known-failures file so the same red never pages anyone again."

**Code (the defect):**
- `bin/sdt:986-988` (`record_known_failures`) returns early:
  `if not patterns or not self.cfg.known_failures:` logs "no known-failures
  file configured; QA's environment ruling not recorded".
- `bin/sdt:1768` (`on_qa`) pops the failure signature before the recording.
  So `regression_open()` (`bin/sdt:1749-1757`) is false for the next red tip,
  and `run_qa_gate()` (`bin/sdt:1733-1747`) dispatches QA again.
- The empty default is in three places: `bin/sdt:127`,
  `docs/config.template.toml:76` (`known_failures = ""`), and
  `.delivery-team/config.toml`, which has no `[qa] known_failures`.
- The drop never reaches the board. `log()` writes stdout only. The ledger's
  `qa_state` reads "environment fault at …" until the next gate overwrites
  it.

**Evidence:** verified by reading the runtime path end to end: `on_qa` →
`housekeep` → `record_known_failures`, which returns early, then
`run_qa_gate` on the next tip, which finds no open signature.

**Consequence:**
- A known environment fault (for example a layer this machine cannot run)
  costs one frontier QA run on every landing, for the rest of this run and
  every later one.
- The owner never sees the ruling recorded anywhere durable.
- QA's promise that "the same red never pages anyone again" is false under
  the default configuration.

**Acceptance criteria:**
- With `[qa] known_failures` unset, an `ENVIRONMENT` ruling is still recorded
  durably.
- The same failure on the next tip is filtered without dispatching QA.
- Where the ruling lands by default is documented in
  `docs/config.template.toml` `[qa]`.
- `tests/test_units.py` or `tests/test_e2e.py` covers an orchestrator with no
  `known_failures` key. After an `ENVIRONMENT` result, a second red tip with
  the same failure starts no QA run, and the pattern is on disk.

**Exact files to change:**
- `bin/sdt`: the `Config` default, `load_config`, `record_known_failures`,
  `known_failure_patterns`.
- `docs/config.template.toml`.
- `tests/test_units.py` or `tests/test_e2e.py`.

**Suggested approach:** give `known_failures` a non-empty default path, so
the charter's sentence holds as written. The orchestrator commits the file
explicit-path, so the default must be committable. This repo's `.gitignore`
ignores `.delivery-team/*` except `profile.md` and `config.toml`, so a default
under `.delivery-team/` needs an exception or a different location.

Coordinate with:
- `P1-known-failure-pattern-masks-new-failures`, which changes the same
  functions.
- Entry 8 of `P3-restatements-contradict-owning-sections`, which adds the
  known-failures write to the charter's housekeeping list.
