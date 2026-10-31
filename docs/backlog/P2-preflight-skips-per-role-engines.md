---
by: qa (consistency-check)
---
# Preflight and `sdt doctor` check only the default engine

**What's wrong:** `config.toml` can route a role to another engine
(`[engine.roles]`), but preflight and `sdt doctor` check only the default
engine. A per-role engine whose CLI is missing passes both. The run then
crashes with a traceback the first time that role is dispatched.

**Spec (canonical):**
- `docs/team-charter.md#role-runs--how-every-role-executes` (lines 134-138):
  "the orchestrator refuses to start until it can mutate: the engine passes
  `sdt doctor` … Any failure is reported as `MUTATIONS-BLOCKED {reason}` and
  nothing is dispatched."
- `#engines--any-coding-cli-through-an-adapter` (lines 145-146): the engine
  is "whichever coding CLI the project's `config.toml` names (`[engine]`, per
  role if it likes)".

**Code (the defect):**
- `bin/sdt:1137`: `preflight()` calls
  `doctor_checks(self.p, self.cfg.engine_default)` only.
- `bin/sdt:1990-1999`: `cmd_doctor()` also checks one engine.
- `bin/sdt:556-564`: `Popen` can raise `FileNotFoundError`, and nothing
  catches it.
- `bin/sdt:2139-2143`: `main()` catches only `SdtError`.

**Evidence (run by this audit):** a stub-engine repo with `[engine.roles]
developer = "ghost"`, whose adapter command is `ghost-cli-not-on-path`.
- `sdt doctor` printed `doctor: ready` (exit 0).
- `sdt run` dispatched the Manager, then exited 1 with `FileNotFoundError:
  [Errno 2] No such file or directory: 'ghost-cli-not-on-path'`, leaving
  `.delivery-team/runs/sdt.pid` behind.

**Consequence:** preflight cannot guarantee what the spec says it does. A
misconfigured per-role engine is not refused up front with
`MUTATIONS-BLOCKED`. Instead the run crashes partway, with role processes
possibly still running and worktrees half set up.

**Acceptance criteria:**
- `doctor_checks` covers the default engine and every engine named in
  `[engine.roles]`, plus the `--engine` override.
- A role's `vision` constraint is checked against its configured engine.
- `sdt doctor` reports every configured engine.
- Preflight raises `MUTATIONS-BLOCKED` on any error before anything is
  dispatched.
- An `OSError` from `Popen` becomes a failed run (`RunResult`), not a crash.
- `tests/test_e2e.py` gains the case above: `sdt doctor` exits 1, and
  `sdt run` exits 2 with `MUTATIONS-BLOCKED` having dispatched nothing.

**Exact files to change:** `bin/sdt` (`doctor_checks`, `cmd_doctor`,
`preflight`, `RoleRun.__init__`), `tests/test_e2e.py`.

**Suggested approach:** loop the existing checks over
`{engine_default, *engine_roles.values()}`.
