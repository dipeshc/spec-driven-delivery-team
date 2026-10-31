# Project profile — `<project name>`

Copy this file to `<repo>/.delivery-team/profile.md` and fill it in. It is the
**prose half** of a project's configuration: what a role reads directly to
judge its work. The machine-read half — gate commands, backlog location,
engine, limits, worktree locations and whether the board is enabled — lives
beside it in `config.toml` (see `docs/config.template.toml`); the orchestrator
hands those values to every role in its run context, so do not repeat them here.

The delivery machinery (the charter, the orchestrator, the roles, the skills)
is **generic and identical for every project**; these two files are the *only*
place a project's own specifics live, and every role reads this one first and
treats it as authoritative.

A section left as `n/a` means "this project has no such requirement" — that is
a valid, complete answer, not an omission. A role must never invent a rule for
a section marked `n/a`, and must never assume a convention from some other
project applies here.

---

## Repo

- **Package manager / runtime:** e.g. `pnpm` + Node 22 / `uv` + Python 3.14
- **Layout:** the packages/apps that exist and what each is, one line each.

## Quality gate

The commands themselves are in `config.toml` `[gate]`. Here, what they do and
do not prove:

- **Not covered:** the gate's blind spots — what even the full gate does not
  compile, boot, or exercise (e.g. an app with no build script, layers that
  need a device or live service). Green means those commands passed, never
  more; roles must not mistake it for broader verification.
- **Notes:** anything load-bearing — tests that need a display, a container, a
  network service, or that are known-slow.

## Backlog

The directory is in `config.toml` `[backlog]`.

- **Conventions doc:** e.g. `docs/backlog.md`, or `n/a` if the convention is
  just "one file per item, priority in the filename."
- **Item lifecycle:** how an item is marked done (e.g. "the landing commit
  deletes the item file"), or `n/a` if the project uses an external tracker.

## Specification source of truth

- **Docs are spec?** yes / no. If yes: which directory, and what a doc-vs-code
  mismatch means (which side is wrong).
- **Docs root:** e.g. `docs/`, or `n/a`.
- **Decision records:** e.g. `docs/decisions/` (ADRs), or `n/a`.
- **Conventions doc:** where this repo's code style, commit-message format, and
  naming conventions live (e.g. `docs/development/conventions.md`), or `n/a` if
  the convention is simply "match the surrounding code and existing git log."

## Repo-wide invariant guards

Tests that are **repo-wide invariants no per-package scope covers** — so
scoped verification silently skips them. The commands are in `config.toml`
`[gate] guards` with their triggers; here, say what each guards and why, so
triage and reviewers can tell when a change hits it.

- `path/to/guard.test.ts` — what it guards, and when it MUST be run (e.g.
  "whenever a change adds or edits test fixtures or sample data").
- `n/a` if the project has none.

## UI surfaces

For visual-QA sweeps (the `ui-inspector` role). Omit or mark `n/a` for a
project with no UI.

- **How to boot the app locally:** the exact command, plus the URL/port.
- **Routes to sweep:** the significant routes, or where the router is defined
  so they can be derived.
- **Viewports:** the widths that matter (e.g. mobile 390, tablet 834, desktop
  1440).
- **Roles / auth states:** the distinct user roles or signed-in/out states that
  change what renders.
- **Themes:** which themes exist (light, dark, both) — a role must not judge
  contrast against a theme the app doesn't implement.

## Exploration log

- **Location:** where feature-exploration spikes are recorded (e.g.
  `docs/exploration.md`), or `n/a` to default to `<docs-root>/exploration.md`.

## Cross-surface parity

If a user-facing change must land on several clients/platforms to be complete:

- **Surfaces:** e.g. web, iOS, Apple TV.
- **Parity ledger:** where an intentional divergence is recorded.
- **Backstop:** the script/test that enforces it.
- `n/a` if the project has a single surface.

## Sanctioned direct-write paths

Paths the owner's session may commit to directly on the main working tree —
housekeeping writes that never go near a branch or a gate. The orchestrator's
own housekeeping (backlog items, `blocked/` moves, the ledger) is sanctioned
by the charter and needs no entry.

- e.g. `docs/backlog/`, `.delivery-team/`
- `n/a` if nothing is written straight to the main tree here.

This list does **not** enumerate direct-lane code paths: a direct-lane change
is not a direct commit — it is implemented on a short-lived branch and
fast-forward-merged after its proof, and the charter's "Scoped writers to the
main working tree" sanctions that path wherever the lane's own preconditions
hold. So `n/a` here means "no housekeeping writes", never "no direct lane".

## Project-specific content rules

Any rule about what may or may not appear in code, docs, tests, or commit
messages that is unique to this project (naming conventions, forbidden
vocabulary, licensing/attribution requirements, placeholder conventions).

- `n/a` if none.

## Verification environment

- Anything a role needs to know to run this project locally: required
  services or data sets, credentials that exist vs. are absent, which test
  layers can/can't be run in the current environment, and the exclusive
  resources (dev-server ports, devices, fixture services) that only one run
  may hold at a time — declare their existence in `config.toml` `[ports]`.
- Whether commits must be signed (the Merge-Clerk's commit-object check
  verifies the signature when they must).
- `n/a` if a plain checkout runs everything.
