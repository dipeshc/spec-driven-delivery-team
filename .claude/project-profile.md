# Project profile — `spec-driven-delivery-team`

This repo dogfoods the framework it ships. The global delivery machinery (the
charter, skills, and agents) is generic; this file holds everything specific to
working on *this* repository.

---

## Repo

- **Root path:** `/Users/dipesh/code/spec-driven-delivery-team`
- **Default branch:** `main`
- **Package manager / runtime:** n/a — no build and no dependencies; the repo is
  Markdown plus one workflow script the Claude Code runtime executes.
- **Layout:**
  - `.claude-plugin/` — plugin manifest.
  - `agents/` — the team's agent definitions.
  - `skills/` — the plugin's skills, one directory per skill.
  - `workflows/` — `consistency-sweep.js`, the parallel spec audit.
  - `docs/` — the spec: `architecture.md` (entry doc), `team-charter.md`,
    `project-profile.template.md`, and `backlog/`.

## Quality gate

- **Scoped:** n/a — there is no test suite; the diff is prose. The reviewer's
  reading against `docs/architecture.md` and `docs/team-charter.md` IS the
  verification.
- **Full:** n/a — the `consistency-check` skill (spec-vs-spec, then
  spec-vs-code over the agent, skill and workflow definitions) is this repo's
  full audit; `/delivery-team:consistency-sweep` runs it across everything.
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
  specify the framework; the agent files under `agents/`, the skills under
  `skills/` and the workflow under `workflows/` implement them. A mismatch means
  the implementing file is wrong —
  unless the change is a deliberate re-decision, which is an owner call and
  updates the spec first. `docs/project-profile.template.md` is a shipped
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
- `.claude/` — this profile.

## Worktree layout

- **Where worktrees are created:** `<repo>/.claude/worktrees/<name>/`
- **Branch naming:** `item/<slug>`
- **Landing style:** fast-forward only, one commit per item.

## Reviewer pool

- n/a — the default single Reviewer.

## Project-specific content rules

- **Stay project-agnostic:** no file may reference any specific consuming
  project, product, or domain the framework has been used on. The only
  permitted usage claim is the README's "thousands of commits" line.
- **External-engine containment:** engine mechanics (invocation, pools, modes,
  engine messages) may appear only in `agents/engine-supervisor.md`; every
  other file may at most point there.

## External implementation engine

- n/a

## Verification environment

- n/a — a plain checkout is everything; there is nothing to run.
