# Architecture — the delivery-team plugin

This is the **specification and entry doc for this repository itself**. The
plugin it describes tells other projects to treat their docs as the spec; this
repo holds itself to the same rule. Where this document and an agent or skill
file disagree, this document is right and the agent/skill file is a bug.

## What this repo is

A harness-agnostic framework implementing an autonomous, docs-driven software
delivery team. Its "code" is the orchestrator under `bin/`, the role prompts
under `roles/`, the engine adapters under `adapters/`, the skills under
`skills/` that let any coding harness drive it, and the tests under `tests/`.
It is also a Claude Code plugin (the manifest under `.claude-plugin/`); surfaces
that only Claude Code can host — the terminal statusline and the parallel
consistency-sweep workflow — live under `extras/claude/`, which the manifest
adds to the plugin's skill and workflow scans; nothing else depends on them.
Its spec is the documents under `docs/`.

## Document roles

| Document | Role |
|---|---|
| `docs/architecture.md` | This file — the design spec and entry doc for the repo. |
| `docs/team-charter.md` | The shared behavioural spec every team agent implements. Agent files reference it rather than restating it; a role-specific twist lives in the role's own file. |
| `docs/profile.template.md` | A shipped artifact for consuming projects: the prose half of a project's configuration. Its section contents describe *consumers*, not this repo — the consistency check audits its structure (references, terminology), never treats its example values as claims about this repo. |
| `docs/config.template.toml` | The machine-read half: every key `bin/sdt` consumes, with its default. Shipped to consumers by `sdt init`. |
| `docs/backlog/` | This repo's own backlog: one file per item, priority in the filename, deleted by the merging commit. |
| `README.md` | The public front door. It summarizes this spec and must never contradict it. |

## Components

| File | Role |
|---|---|
| `bin/sdt` | The orchestrator: the only component that talks to an engine. Triages through the Manager role, creates worktrees, dispatches Developers, batches reviews, lands what the Merge-Clerk verified, runs the full gate on every new tip (direct-lane landings included), files what roles return, blocks what triage blocks, removes landed worktrees with the cherry proof, writes the ledger on every tick. Never pushes. Standard library only. |
| `adapters/<engine>.toml` | How to run one coding CLI headless: command, model flag per tier, add-dir style, final-message extraction, whether it is tested, has network, can see images. `claude`, `agy`, `codex`, `gemini`, `cursor`, `opencode` and `copilot` ship, each saying whether a real run has landed on it; a project may add its own under `.delivery-team/adapters/`. |
| `roles/manager.md` | Triage and decisions, called by the orchestrator at four points: intake, a BLOCKED developer, an exhausted review loop, a blocked landing. Returns JSON decisions; runs no loop and does no work. |
| `roles/developer.md` | Implements exactly one item (or one triaged group) in the worktree it was given, as one commit, rebased before submitting. Never merges. |
| `roles/reviewer.md` | Judges correctness and standards for a batch of READY items, re-verifies with the reverse-dependency slice. Emits verdicts only; writes nothing outside its own worktree. |
| `roles/merge-clerk.md` | Judges landability: rebases a trivially-behind branch by cherry-pick + range-diff, re-verifies, checks the commit object, and reports the sha as LANDABLE. The orchestrator performs the fast-forward. |
| `roles/qa.md` | Root-causes a new full-gate failure on a landed tip and returns the regression item to file. Never fixes anything. The gate itself is run by the orchestrator. |
| `roles/researcher.md` | Turns an item that needs investigation into actionable item(s), returned for filing. |
| `roles/consistency-check.md` | The two-phase spec audit: spec-vs-spec, then spec-vs-code. Returns findings as items; fixes nothing. Run on the QA cadence and on demand through the skill. |
| `roles/exploration.md` | Owner-run specialist for feature-spike waves, outside the pipeline. |
| `roles/ui-inspector.md` | Owner-run specialist for visual QA of a project's rendered UI; needs a vision-capable engine. |
| `skills/team/SKILL.md` | How a harness session runs a delivery: lane routing, the direct lane done in-session, the team lane via `sdt run`, status via `sdt status`, filing items. |
| `skills/team/exploration-and-promotion.md` | How exploration runs and how a kept spike is promoted through the pipeline. |
| `skills/board/SKILL.md` | Opens the progress board on demand (`sdt board`). Zero-runtime; safe to open with no run active. |
| `skills/consistency-check/SKILL.md` | Runs the consistency-check role on demand (`sdt role consistency-check --file-items`). |
| `extras/claude/skills/statusline/SKILL.md` | Claude-only: installs, updates, or removes the terminal statusline, chaining onto any existing statusline rather than clobbering it. |
| `assets/dashboard.html` | The zero-runtime progress board: a self-contained browser page copied beside the orchestrator's `state.js` and opened over `file://`. Live-polls the state ledger and renders the pipeline board, agent rail, and event feed. A renderer, never a source of truth. |
| `extras/claude/skills/statusline/statusline.sh` | Claude-only, zero-runtime: a pure-POSIX-shell script that reads Claude Code's statusline stdin JSON, finds the project's state ledger, and prints up to two glanceable lines. A renderer, never a source of truth. |
| `extras/claude/workflows/consistency-sweep.js` | Claude-only: the whole-spec audit as a parallel workflow — a finding class per agent, each finding put to an independent skeptic, survivors filed in one serialized step. Invoked as `/delivery-team:consistency-sweep`. |
| `tests/` | The orchestrator's unit tests and an end-to-end run on a scripted stub engine (`tests/fake_engine.py`, adapter `tests/adapters/fake.toml`) that exercises every pipeline path without a model. |

## Invariants

These bind every component; a component contradicting one is defective.

1. **Docs drive design.** For a project that declares docs-as-spec, the docs
   are the source of truth: a doc-vs-code mismatch is a code bug, spec edits
   ship in the same commit as the behaviour they describe, and agents sharpen
   docs but never re-decide them (decisions are the owner's).
2. **One writer for code, per lane.** Code reaches a project's main working
   tree only by `merge --ff-only`, one commit per item, linear history — and
   only one writer per lane performs that merge: the orchestrator, landing the
   sha the Merge-Clerk verified, for team-lane work, and for a direct-lane
   change (invariant 3) the single session that did the work, under the proof
   obligations the charter's "Scoped writers" entry states. Beside those two
   sits the orchestrator's scoped housekeeping (charter, "Scoped writers"),
   which edits no code, and no role writes to the main working tree at all.
3. **Risk-routed lanes.** Small, single-area changes take the direct lane; the
   full pipeline is reserved for work whose risk earns it. Verification effort
   scales with risk, not habit.
4. **Capability tiers are pinned, not self-declared.** Each role file declares
   its tier (`frontier` for Manager, Reviewer, Merge-Clerk, QA, Researcher and
   the consistency check; `mid` by default for a Developer, raised by triage
   for judgment-heavy items), and the orchestrator chooses the model for that
   tier from the adapter and the project's config. No role verifies or
   declares its own model.
5. **Engines are interchangeable and contained.** Any coding CLI with a
   headless mode can be the engine, described by one adapter file; nothing
   outside `adapters/` and the orchestrator's adapter loader knows one engine
   from another. Every run is confined to its worktree plus the directories the
   orchestrator grants, never by the engine's own sandbox, and engine output is
   an untrusted diff that passes the same review and gates as any other.
6. **Project-agnostic core.** The charter, roles, adapters and orchestrator are
   identical for every project; everything project-specific lives in the
   consuming repo's `.delivery-team/config.toml` (machine-read) and
   `.delivery-team/profile.md` (prose), and the orchestrator hands the former
   to every role in its run context.
7. **State lives in git.** Backlog items are files; work-in-flight is branches
   and worktrees; an item is done when the merging commit deletes its file. Any
   agent's death is recoverable from git alone.
8. **Verification is honest.** Roles report the exact commands they ran and
   their outcomes; a verification not run is reported as not run.
9. **One execution path.** Only the orchestrator talks to an engine, through an
   adapter, and only the orchestrator writes the main working tree — landing
   the sha the Merge-Clerk verified, filing the items roles return, blocking
   what triage blocks. A role never spawns, messages or resumes another role,
   never writes outside the worktree it was given, and never pushes; the
   orchestrator never pushes either.

## Changing this repo

This repo consumes its own process: `.delivery-team/profile.md` declares
docs-as-spec with `docs/` as the docs root, and work is filed into
`docs/backlog/`. A change that alters behaviour specified here — a role's
responsibilities, an invariant, a message flow — updates this document (and the
charter where the rule is shared) in the same commit. The `consistency-check`
role is the audit: phase 1 checks these documents against each other, phase 2
checks the orchestrator, role, adapter and skill definitions against them, and
the tests under `tests/` pin the orchestrator's behaviour to what the charter
says.
