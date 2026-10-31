---
by: qa (consistency-check)
---
# Engine-specific knowledge outside `adapters/`

**What's wrong:** five places outside `adapters/` and the adapter loader name
a specific engine, its invocation behaviour, or its model names.

**Spec (canonical):**
- `docs/architecture.md#invariants`, invariant 5 (lines 81-84): "nothing
  outside `adapters/` and the orchestrator's adapter loader knows one engine
  from another."
- `.delivery-team/profile.md#project-specific-content-rules`, Engine
  containment: "how a specific coding CLI is invoked (its flags, model names,
  output shape) may appear only in that engine's adapter under `adapters/`;
  every other file speaks of 'the engine' and at most points there."

**Instances:**
1. `bin/sdt:1861-1866` (`doctor_checks`): `if adapter.name == "claude"`
   inspects `.claude/settings.json` for hooks.
2. `bin/sdt:1867-1868`: `if adapter.name == "codex"` reports "codex exec
   needs a git repository". `adapters/codex.toml` says "`doctor` checks
   that".
3. `roles/ui-inspector.md:15`: `engines: [claude, gemini]`. This duplicates
   the adapters' own `vision = true` (`adapters/claude.toml:9`,
   `adapters/gemini.toml:11`). The role's `vision: true` (line 14) already
   enforces that requirement through `bin/sdt:718-719`.
4. `docs/config.template.toml:44-46`: `# frontier = "opus"`,
   `# mid = "sonnet"`, `# small = "haiku"` are one engine's model names in a
   shipped template.
5. `docs/team-charter.md:330`: the ledger example's `model: "opus"`.

**Canonical resolution:** the invariant. Engine-specific preconditions become
adapter fields that the loader reads, and every other file uses neutral
placeholders.

**Consequence:**
- Adding or changing an engine means editing the orchestrator and a role
  file, which is exactly what the invariant forbids.
- The ui-inspector's hard-coded list refuses a project adapter for a
  vision-capable engine under `.delivery-team/adapters/`.

**Acceptance criteria:**
- `doctor_checks` compares against no adapter name. Both checks are driven by
  adapter fields (for example a `requires_git_repo` boolean and a
  `project_hooks_file` path) that `adapters/codex.toml` and
  `adapters/claude.toml` declare and `load_adapter` parses.
- `roles/ui-inspector.md` frontmatter has no `engines:` line.
- The `[engine.tiers]` examples in `docs/config.template.toml` and the
  charter's ledger example use placeholders, e.g. `"<model id>"`.
- `tests/test_units.py`: the new adapter fields produce the same doctor
  findings for a stub adapter that declares them as the name checks produce
  today.

**Exact files to change:** `bin/sdt` (`Adapter`, `load_adapter`,
`doctor_checks`), `adapters/claude.toml`, `adapters/codex.toml`,
`roles/ui-inspector.md`, `docs/config.template.toml`, `docs/team-charter.md`,
`tests/test_units.py`.

**Suggested approach:** `Role.engines` support can stay in the loader for
project-local roles, but no shipped role should use it.
