# Add `sdt sweep`, the harness-neutral whole-spec audit

**What's wrong:** the whole-spec parallel audit exists only as a Claude Code
workflow (`extras/claude/workflows/consistency-sweep.js`); every other
harness can run the incremental consistency check but not the sweep that
fans a finding class out per agent and puts every finding to a skeptic before
filing.

**Evidence:** `extras/claude/workflows/consistency-sweep.js` uses the
Workflow tool's `agent()`, `pipeline()` and `parallel()`; `bin/sdt` has a
`Project.start_run()` primitive and concurrent `RoleRun` handling in `Orchestrator`
but no `sweep` command. `docs/architecture.md`'s components table lists the
workflow as Claude-only.

**Consequence:** the framework's "works on any harness" claim has one
Claude-only audit path, and the parallel sweep's refute-before-file
discipline is unavailable elsewhere.

**Acceptance criteria:**
- `sdt sweep` runs, on the configured engine: a map step (one
  `consistency-check` run with payload `{"phase": "map"}` returning the file
  inventory and applicability), then one audit run per finding class in
  parallel (payload `{"phase": "audit", "class": <name>, "files": [...]}`),
  then one skeptic run per finding (payload `{"phase": "verify", "finding":
  {...}}`) returning `{"verdict": "confirmed" | "refuted", "reason"}`, then
  files the confirmed findings as items in one commit.
- The finding classes are the six of the consistency-check role's phase 1
  plus `spec-vs-code` when docs are spec.
- `roles/consistency-check.md` documents the `phase` payloads it accepts and
  that with no `phase` it runs the full incremental pass as today.
- `tests/test_e2e.py` runs `sdt sweep` on the stub engine (the stub answers
  each phase) and asserts the confirmed findings are filed and the refuted
  ones are not.
- `extras/claude/workflows/consistency-sweep.js` is deleted, the manifest's
  `workflows` key removed, and the architecture and README no longer mention
  it; `docs/architecture.md` lists `sdt sweep` beside the role.

**Exact files to change:** `bin/sdt`, `roles/consistency-check.md`,
`tests/fake_engine.py`, `tests/test_e2e.py`, `extras/claude/workflows/`
(delete), `.claude-plugin/plugin.json`, `docs/architecture.md`, `README.md`.

**Suggested approach:** reuse `Project.start_run()` and a small poll loop over
a list of `RoleRun`s (the orchestrator's `tick()` shows the pattern) rather
than threads; bound parallelism with `limits.max_parallel_developers`.
