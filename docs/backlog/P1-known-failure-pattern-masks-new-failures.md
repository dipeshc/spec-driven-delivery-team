---
by: qa (consistency-check)
---
# A known-failure pattern masks every other failure in the same gate command

*Line numbers are at `547befb`.*

**What's wrong:** the full gate filters known failures per *command*, not per
failure. If a failing command's output contains any known-failure pattern, the
whole command counts as a known failure. A new failure in the same command is
then masked, the tip reads green, and QA is never dispatched.

**Spec (canonical):**
- `docs/config.template.toml` `[qa]` (lines 74-75): the known-failures file
  names "failures that are already known; only a failure matching none of them
  is a regression."
- `roles/qa.md#why-you-exist--the-fail-closed-full-run` (lines 38-42): the
  full run "is **fail-closed** … never a silent green — and failures matching
  the known-failures file are filtered out before you are involved. You are
  dispatched only for what remains: a **new** red."
- `docs/team-charter.md#message-schemas--the-canonical-payload-table`
  (line 594): `REGRESSION-REQUEST` is "sent only on a **new** full-gate
  failure; the orchestrator runs the gate itself … and filters the
  known-failures file".

**Code (the defect):** `bin/sdt:977-981` (`Project.run_full_gate`):

```python
if proc.returncode != 0:
    if any(p in output for p in known):
        fh.write("(known failure)\n")
        continue
    new_failures.append(cmd)
```

One pattern anywhere in a command's output clears the whole command. That
includes a crash whose output happens to print a known test's name.

**Evidence (run by this audit):** in a scratch repo at `5c1e96c` (this code is unchanged at `547befb`):
- `[qa] known_failures = "known.txt"`, and `known.txt` holds
  `test_known_flaky`.
- `[gate] full` is one command that prints
  `FAILED tests/a.py::test_known_flaky` and
  `FAILED tests/b.py::test_brand_new_regression`, then exits 1.
- `Project.run_full_gate()` returned `(True, [])`. The log shows `[exit 1]`,
  then `(known failure)`.

**Consequence:**
- A suite with one tolerated known failure becomes blind to every new failure
  in the same command, for as long as the known one keeps failing.
- The default branch goes red with nobody paged.
- The direct lane depends on this gate as its independent verification, so a
  direct-lane regression lands unseen.
- This repo configures no known-failures file, so here the defect is latent.
  It bites every consumer that records an environment ruling.

**Acceptance criteria:**
- A failing command is filtered as known only when every failure in its output
  is covered by a known pattern. When the output's failures cannot be told
  apart, the command fails closed and counts as new.
- `tests/test_units.py` covers `run_full_gate` in three cases:
  - a command whose only failure is known → green;
  - a command with a known failure and an unknown one → red, with that
    command in `failures`;
  - a nonzero exit whose output holds a known pattern but no failure line (a
    crash) → red.
- If the fix changes how a pattern must match, `roles/qa.md`, the config
  template's `[qa]` comment and the charter's `REGRESSION-REQUEST` row say
  so, and keep QA's "be exact" rule.

**Exact files to change:**
- `bin/sdt`: `Project.run_full_gate`, and `known_failure_patterns` if the file
  format gains structure.
- `tests/test_units.py`.
- `docs/config.template.toml` `[qa]` and `roles/qa.md`, only if the matching
  rule changes.

**Suggested approach:** the gate cannot parse every runner's output, so key
the filter on what it can prove. For example, remove every line that a known
pattern matches. If the output still holds a failure-shaped line, or no failure
line was matched at all, the command counts as new. Whatever the rule, it must
fail closed. `P2-environment-ruling-lost-without-known-failures-file` changes
the same functions and could be grouped with this item.
