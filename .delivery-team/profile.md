# Project profile — `spec-driven-delivery-team`

This repo dogfoods the framework it ships. The global delivery machinery (the
charter, skills, and agents) is generic; this file holds everything specific to
working on *this* repository.

---

## Repo

- **Root path:** `/Users/dipesh/code/spec-driven-delivery-team`
- **Default branch:** `main`
- **Package manager / runtime:** `python3` 3.11+ for the orchestrator (standard
  library only); `uv` for the development tooling (`ruff`, `mypy`, `pytest`)
  declared in `pyproject.toml`. The rest of the repo is Markdown.
- **Layout:**
  - `.claude-plugin/` — plugin manifest (the Claude Code packaging).
  - `.delivery-team/` — this profile and `config.toml` (tracked) beside the
    run's git-ignored runtime state.
  - `bin/sdt` — the orchestrator.
  - `adapters/` — one TOML per engine.
  - `roles/` — the team's role prompts.
  - `skills/` — the skills, one directory per skill.
  - `tests/` — the orchestrator's tests and the stub engine.
  - `extras/claude/` — Claude-only surfaces: the statusline skill and script,
    and `workflows/consistency-sweep.js`, the parallel spec audit.
  - `docs/` — the spec: `architecture.md` (entry doc), `team-charter.md`,
    `profile.template.md`, `config.template.toml`, and `backlog/`.

## Quality gate

- **Scoped / Full:** the commands in `config.toml` `[gate]` (ruff, mypy and
  pytest over `bin/sdt` and `tests/`). They verify the orchestrator only.
- **Not covered:** the role prompts, skills and docs are prose, so the gate
  cannot exercise them; the reviewer's reading against `docs/architecture.md`
  and `docs/team-charter.md` IS their verification, and the
  `consistency-check` role (spec-vs-spec, then spec-vs-code over the role,
  skill and adapter files) is this repo's audit of them.
- **Not covered:** everything not readable — there is no automated gate, so
  nothing is compiled, run, or booted; reading against the spec is the entire
  verification.
- **Notes:** every relative link and `${CLAUDE_PLUGIN_ROOT}` path referenced in
  a changed file must resolve to a file that exists in the repo.

## Backlog

- **Location:** `docs/backlog/` (per-item files, priority in the filename,
  `P0`–`P3`).
- **Conventions doc:** n/a — the charter's "Backlog conventions" section is the
  convention.
- **Item lifecycle:** the merging commit deletes the item file.

## Specification source of truth

- **Docs are spec?** Yes. `docs/architecture.md` and `docs/team-charter.md`
  specify the framework; the orchestrator under `bin/`, the role files under
  `roles/`, the adapters, the skills and the Claude-only extras under
  `extras/claude/` implement them. A mismatch means
  the implementing file is wrong —
  unless the change is a deliberate re-decision, which is an owner call and
  updates the spec first. `docs/profile.template.md` is a shipped
  artifact whose example values describe consuming projects, not this repo.
- **Docs root:** `docs/`
- **Decision records:** n/a
- **Conventions doc:** n/a — match the surrounding prose style and the existing
  git log (Conventional Commits).

## Repo-wide invariant guards

- n/a — no automated guards; the containment and agnosticism rules below are
  enforced by review and the consistency check.

## QA watch loop

- n/a — no watch loop; QA (or the root, on request) runs the
  `consistency-check` skill directly.

## UI surfaces

- n/a — no UI.

## Exploration log

- n/a

## Cross-surface parity

- n/a — single surface.

## Sanctioned direct-write paths

- `docs/backlog/` — filed items.
- `.delivery-team/` — this profile.

## Worktree layout

- **Where worktrees are created:** `<repo>/.delivery-team/worktrees/<name>/`
- **Branch naming:** `item/<slug>`
- **Landing style:** fast-forward only, one commit per item.

## Reviewer pool

- n/a — the default single Reviewer.

## Project-specific content rules

- **Stay project-agnostic:** no file may reference any specific consuming
  project, product, or domain the framework has been used on. The only
  permitted usage claim is the README's "thousands of commits" line.
- **Engine containment:** how a specific coding CLI is invoked (its flags,
  model names, output shape) may appear only in that engine's adapter under
  `adapters/`; every other file speaks of "the engine" and at most points
  there.

## Verification environment

- `uv` and `python3` 3.11+ are present; a plain checkout plus `uv sync` runs
  the whole gate. Commits on this repository are signed; the merge-clerk's
  commit-object check requires a verified signature.
