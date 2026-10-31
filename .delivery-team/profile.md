# Project profile — `spec-driven-delivery-team`

This repo dogfoods the framework it ships. The delivery machinery (the
charter, the orchestrator, the roles, the skills) is generic; this file and
`config.toml` beside it hold everything specific to working on *this*
repository.

---

## Repo

- **Package manager / runtime:** `python3` 3.11+ for the orchestrator (standard
  library only); `uv` for the development tooling (`ruff`, `mypy`, `pytest`)
  declared in `pyproject.toml`. Beyond `bin/sdt` and `tests/`, the repo is
  mostly Markdown, plus a POSIX shell script and JavaScript (the gate's
  blind spots are listed under Quality gate → Not covered).
- **Layout:**
  - `.claude-plugin/` — plugin manifest (the Claude Code packaging).
  - `.delivery-team/` — this profile and `config.toml` (tracked) beside the
    run's git-ignored runtime state.
  - `bin/sdt` — the orchestrator.
  - `adapters/` — one TOML per engine.
  - `roles/` — the team's role prompts.
  - `skills/` — the skills, one directory per skill.
  - `assets/` — the progress board page (`dashboard.html`).
  - `tests/` — the orchestrator's tests and the stub engine.
  - `extras/claude/` — Claude-only surfaces: the statusline skill and script,
    and `workflows/consistency-sweep.js`, the parallel spec audit.
  - `docs/` — the spec: `architecture.md` (entry doc), `team-charter.md`,
    `profile.template.md`, `config.template.toml`, and `backlog/`.

## Quality gate

- **Not covered:** the role prompts, skills, adapters and docs are prose, so
  the gate (ruff, mypy and pytest over `bin/sdt` and `tests/`) cannot
  exercise them; the reviewer's reading against `docs/architecture.md` and
  `docs/team-charter.md` IS their verification, and the `consistency-check`
  role (spec-vs-spec, then spec-vs-code over the role, skill and adapter
  files) is this repo's audit of them. No adapter is exercised against a real
  engine by the gate: the end-to-end test runs on the stub engine only.
  Two executable files are also outside the gate (the statusline script is
  covered by a test in `tests/test_units.py`); the reviewer verifies them
  instead:
  - `assets/dashboard.html` — the board page's JavaScript; open it on a
    ledger and check it renders.
  - `extras/claude/workflows/consistency-sweep.js` — the sweep workflow,
    while it exists; read it against the consistency-check role.
- **Notes:** every relative link and every path a file names must resolve to
  a file that exists in the repo.

## Backlog

- **Conventions doc:** n/a — the charter's "Backlog conventions" section is the
  convention.
- **Item lifecycle:** the landing commit deletes the item file.

## Specification source of truth

- **Docs are spec?** Yes. `docs/architecture.md` and `docs/team-charter.md`
  specify the framework; the orchestrator under `bin/`, the role files under
  `roles/`, the adapters, the skills and the Claude-only extras under
  `extras/claude/` implement them. A mismatch means the implementing file is
  wrong — unless the change is a deliberate re-decision, which is an owner
  call and updates the spec first. `docs/profile.template.md` and
  `docs/config.template.toml` are shipped artifacts whose example values
  describe consuming projects, not this repo.
- **Docs root:** `docs/`
- **Decision records:** n/a
- **Conventions doc:** n/a — match the surrounding prose style and the existing
  git log (Conventional Commits).

## Repo-wide invariant guards

- n/a — no automated guards beyond the gate; the containment and agnosticism
  rules below are enforced by review and the consistency check.

## UI surfaces

- n/a — no UI.

## Exploration log

- n/a

## Cross-surface parity

- n/a — single surface.

## Sanctioned direct-write paths

- `docs/backlog/` — filed items.
- `.delivery-team/` — this profile and `config.toml`.

## Project-specific content rules

- **Stay project-agnostic:** no file may reference any specific consuming
  project, product, or domain the framework has been used on. The only
  permitted usage claim is the README's "thousands of commits" line.
- **Engine containment:** how a specific coding CLI is invoked (its flags,
  model names, output shape) may appear only in that engine's adapter under
  `adapters/`; every other file speaks of "the engine" and at most points
  there. The exception is `extras/claude/`, which is Claude-only by design and
  says so.

## Verification environment

- `uv` and `python3` 3.11+ are present; a plain checkout plus `uv sync` runs
  the whole gate. Commits on this repository are signed; the merge-clerk's
  commit-object check requires a verified signature.
