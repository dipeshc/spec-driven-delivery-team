# Project profile — `<project name>`

Copy this file to `<repo>/.delivery-team/profile.md` and fill it in. The
global delivery machinery (the delivery-team plugin: its charter, skills,
and agents) is **generic and identical for every project**; this file is the
*only* place a project's own specifics live, and every agent reads it first
and treats it as authoritative.

A section left as `n/a` means "this project has no such requirement" — that is
a valid, complete answer, not an omission. An agent must never invent a rule
for a section marked `n/a`, and must never assume a convention from some other
project applies here.

---

## Repo

- **Root path:** `/absolute/path/to/repo`
- **Default branch:** `main`
- **Package manager / runtime:** e.g. `pnpm` + Node 22 / `uv` + Python 3.14
- **Layout:** the packages/apps that exist and what each is, one line each.

## Quality gate

The exact commands that must pass before any change is submitted. Give the
scoped (per-package) form and the full form separately — scoped is the default
for a normal change; full is for cross-cutting work and the QA loop.

- **Scoped:** e.g. `pnpm --filter <pkg> typecheck && pnpm --filter <pkg> test`
- **Full:** e.g. `pnpm typecheck && pnpm test && pnpm build`
- **Not covered:** the gate's blind spots — what even the full gate does not
  compile, boot, or exercise (e.g. an app with no build script, layers that
  need a device or live service). Green means these commands passed, never
  more; agents must not mistake it for broader verification.
- **Notes:** anything load-bearing — tests that need a display, a container, a
  network service, or that are known-slow.

## Backlog

- **Location:** e.g. `docs/backlog/` (per-item files, priority in the filename)
- **Conventions doc:** e.g. `docs/backlog.md`, or `n/a` if the convention is
  just "one file per item."
- **Item lifecycle:** how an item is marked done (e.g. "the merging commit
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
scoped verification silently skips them. Keep this list short and named; each
entry says what triggers it.

- `path/to/guard.test.ts` — what it guards, and when it MUST be run (e.g.
  "whenever a change adds or edits test fixtures or sample data").
- `n/a` if the project has none.

## QA watch loop

- **Runner script:** the project's own watch-and-test script (e.g.
  `scripts/qa/watch-and-test.sh`) — a shell loop that pulls each new
  default-branch tip, runs the **full** gate, and wakes the QA agent only on a
  new failure or a green heartbeat. Per-project by nature (paths, test
  commands, log parsing); the loop's *design* and exit-code contract are in the
  QA agent definition.
- **Known-failures file:** where already-known/accepted failures are recorded so
  the loop wakes on *new* ones only (e.g. `scripts/qa/known-failures.txt`).
- `n/a` if this project has no watch loop — QA then runs the full gate on
  demand instead.

## UI surfaces

For visual-QA sweeps (the `ui-inspector` agent). Omit or mark `n/a` for a
project with no UI.

- **How to boot the app locally:** the exact command, plus the URL/port.
- **Routes to sweep:** the significant routes, or where the router is defined
  so they can be derived.
- **Viewports:** the widths that matter (e.g. mobile 390, tablet 834, desktop
  1440).
- **Roles / auth states:** the distinct user roles or signed-in/out states that
  change what renders.
- **Themes:** which themes exist (light, dark, both) — an agent must not judge
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

Paths the root/orchestrating instance may commit to directly on the main
working tree — housekeeping writes that never go near a branch or a gate.

- e.g. `docs/backlog/`, `scripts/qa/`, `.delivery-team/`
- `n/a` if nothing is written straight to the main tree here.

This list does **not** enumerate direct-lane code paths: a direct-lane change
is not a direct commit — it is implemented on a short-lived branch and
fast-forward-merged after its proof, and the charter's "Scoped writers to the
main working tree" sanctions that path wherever the lane's own preconditions
hold. So `n/a` here means "no housekeeping writes", never "no direct lane".

## Worktree layout

- **Where worktrees are created:** e.g. `<repo>/.delivery-team/worktrees/<name>/`
- **Branch naming:** e.g. `item/<slug>`
- **Landing style:** e.g. fast-forward only, one commit per item.

## Progress board

The live browser board the Manager feeds while a run is in flight (see the
charter's "Progress ledger" section). The Manager writes its machine-readable
state to `state.js` here on every reconcile, the team skill copies the page in
and opens it once per run, and `/delivery-team:board` reopens it on demand. All
of it is runtime housekeeping under `.delivery-team/` — git-ignored, never committed.

- **Where the board lives:** the default is `<repo>/.delivery-team/progress/`
  (`state.js` plus a copied `dashboard.html`). Name a different directory only if
  this project needs one.
- `n/a` to turn the board off — the Manager then skips the state write and the
  skills skip opening the page. A run still works exactly the same; only the
  visual surface is absent.

## Reviewer pool

- **Instance count:** the framework default is a single Reviewer. Set a higher
  number here only if this project's dev throughput genuinely needs more than
  one Reviewer draining the queue in parallel.
- `n/a` to take the default of one.

## Project-specific content rules

Any rule about what may or may not appear in code, docs, tests, or commit
messages that is unique to this project (naming conventions, forbidden
vocabulary, licensing/attribution requirements, placeholder conventions).

- `n/a` if none.

## External implementation engine

An optional, separate coding CLI on its own account/quota that the team may
drive for implementation and advisory reviews (see the plugin's
`engine-supervisor` agent — everything engine-related lives there). Most
projects leave this `n/a`; with it `n/a` or absent, engines do not exist for a
run and no agent will mention or plan around one.

- **Engine CLI:** the command name, or a pointer to an owner-level engine
  config that holds it.
- **Pools and model IDs:** the canonical model IDs per pool (or the pointer to
  the owner-level config that names them).
- **Reserved work classes:** work that must stay on the primary model
  regardless (e.g. anything security/auth/crypto).
- **Advisory reviews:** yes/no — whether team-lane changes get a non-gating
  external second opinion.
- `n/a` if this project uses no external engine.

## Verification environment

- Anything an agent needs to know to run this project locally: required
  services or data sets, credentials that exist vs. are absent, and which
  test layers can/can't be run in the current environment.
- `n/a` if a plain checkout runs everything.
