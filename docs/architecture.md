# Architecture — the delivery-team plugin

This is the **specification and entry doc for this repository itself**. The
plugin it describes tells other projects to treat their docs as the spec; this
repo holds itself to the same rule. Where this document and an agent or skill
file disagree, this document is right and the agent/skill file is a bug.

## What this repo is

A [Claude Code plugin](https://code.claude.com/docs/en/plugins.md) implementing
an autonomous, docs-driven software delivery team. Its "code" is the agent
definitions under `agents/`, the skills under `skills/`, and the plugin
manifest under `.claude-plugin/`. Surfaces that only Claude Code can host — the
terminal statusline and the parallel consistency-sweep workflow — live under
`extras/claude/`, which the manifest adds to the plugin's skill and workflow
scans; nothing else depends on them. Its spec is the documents under `docs/`.

## Document roles

| Document | Role |
|---|---|
| `docs/architecture.md` | This file — the design spec and entry doc for the repo. |
| `docs/team-charter.md` | The shared behavioural spec every team agent implements. Agent files reference it rather than restating it; a role-specific twist lives in the role's own file. |
| `docs/project-profile.template.md` | A shipped artifact for consuming projects. Its section contents describe *consumers*, not this repo — the consistency check audits its structure (references, terminology), never treats its example values as claims about this repo. |
| `docs/backlog/` | This repo's own backlog: one file per item, priority in the filename, deleted by the merging commit. |
| `README.md` | The public front door. It summarizes this spec and must never contradict it. |

## Components

| File | Role |
|---|---|
| `agents/manager.md` | Singleton orchestrator: triages the backlog, dispatches Developers, routes reviews and merges, supervises liveness and scope. Never does the work itself. |
| `agents/developer.md` | Implements exactly one backlog item (or one assigned related group) per dispatch, in its own worktree, as one commit. Never merges. |
| `agents/reviewer.md` | Judges correctness and standards, re-verifies with the reverse-dependency slice. Emits verdicts only; never writes anything, anywhere. One instance by default. |
| `agents/merge-clerk.md` | Singleton, the only writer of team-lane code to the default branch: lands approved branches ff-only, rebasing trivially-behind branches itself via cherry-pick + range-diff. |
| `agents/qa.md` | Singleton guardian: rides the project's watch loop running the full gate on every default-branch tip, files regressions, runs the consistency cadence. Never fixes anything. |
| `agents/engine-supervisor.md` | Opt-in, small-model supervisor of an external engine. The **only** file in the repo that describes external-engine mechanics. |
| `agents/exploration.md` | Root-owned specialist for feature-spike waves, outside the pipeline. |
| `agents/ui-inspector.md` | Root-owned specialist for visual QA of a project's rendered UI. |
| `skills/team/SKILL.md` | How the root instance runs a delivery: lane routing, spawning the Manager, status heartbeat, watchdog, recovery. |
| `skills/team/exploration-and-promotion.md` | How exploration runs and how a kept spike is promoted through the pipeline. |
| `skills/board/SKILL.md` | Opens the progress board on demand, copying the page into place if missing. Zero-runtime, shell and git only; safe to open with no run active. |
| `extras/claude/skills/statusline/SKILL.md` | Installs, updates, or removes the terminal statusline: copies the script to a stable user-level path and wires `statusLine` in `~/.claude/settings.json`, chaining onto any existing statusline rather than clobbering it. User-level surface; needs no per-project profile change. |
| `skills/consistency-check/SKILL.md` | The two-phase spec audit: spec-vs-spec, then spec-vs-code. Owns the method — the applicability gate, the finding classes, how a contradiction is resolved on paper, and the filing rules. Files findings; fixes nothing. |
| `assets/dashboard.html` | The zero-runtime progress board: a self-contained browser page copied beside the Manager's `state.js` and opened over `file://`. Live-polls the state ledger and renders the pipeline board, agent rail, and event feed. A renderer, never a source of truth. |
| `extras/claude/skills/statusline/statusline.sh` | The zero-runtime progress statusline: a pure-POSIX-shell script that reads the caller's stdin JSON, finds the project's state ledger, and prints up to two glanceable lines — the run aggregate and the item most worth attention. No Node, Python, jq, or network, and no git read; absent, stale, or malformed state degrade to silence. A renderer, never a source of truth. |
| `extras/claude/workflows/consistency-sweep.js` | Runs that audit as a whole-spec sweep: a finding class per agent in parallel, each finding put to an independent skeptic that tries to refute it, survivors filed in one serialized step. Owns the fan-out only; the method stays in the skill. Invoked on demand as `/delivery-team:consistency-sweep`; QA's cadence keeps calling the skill directly, since a subagent cannot launch a workflow. |

## Invariants

These bind every component; a component contradicting one is defective.

1. **Docs drive design.** For a project that declares docs-as-spec, the docs
   are the source of truth: a doc-vs-code mismatch is a code bug, spec edits
   ship in the same commit as the behaviour they describe, and agents sharpen
   docs but never re-decide them (decisions are the owner's).
2. **One writer for code, per lane.** Code reaches a project's main working
   tree only by `merge --ff-only`, one commit per item, linear history — and
   only one agent per lane performs that merge: the Merge-Clerk for team-lane
   work, and for a direct-lane change (invariant 3) the single agent that did
   the work, under the proof obligations the charter's "Scoped writers" entry
   states. Beside those two sits a short list of scoped housekeeping writers
   (charter, "Scoped writers"); none of them edit code, and no other role
   writes to the main working tree at all.
3. **Risk-routed lanes.** Small, single-area changes take the direct lane; the
   full pipeline is reserved for work whose risk earns it. Verification effort
   scales with risk, not habit.
4. **Capability gate.** Judgment roles (Manager, Reviewer, Merge-Clerk, QA,
   Researcher) require a frontier model and refuse to run otherwise. The
   Developer and the Engine-Supervisor are exempt.
5. **External engines are opt-in and contained.** Engine mechanics live only in
   `agents/engine-supervisor.md`; every other file may at most *point* there.
   Engines exist for a run only when the consuming project's profile declares
   one; engine output is always an untrusted contributor diff that passes the
   same review and gates as any other change.
6. **Project-agnostic core.** The charter, agents, and skills are identical for
   every project and contain nothing project-specific — no references to any
   particular consuming project, product, or domain. Everything
   project-specific lives in the consuming repo's `.delivery-team/profile.md`,
   whose shape is defined by the template.
7. **State lives in git.** Backlog items are files; work-in-flight is branches
   and worktrees; an item is done when the merging commit deletes its file. Any
   agent's death is recoverable from git alone.
8. **Verification is honest.** Agents report the exact commands they ran and
   their outcomes; a verification not run is reported as not run. Sunset-tagged
   workarounds (`DELETE WHEN …`) mark rules that exist only to route around a
   current harness limitation, so they are deleted when the cause is gone.

## Changing this repo

This repo consumes its own process: `.delivery-team/profile.md` declares
docs-as-spec with `docs/` as the docs root, and work is filed into
`docs/backlog/`. A change that alters behaviour specified here — a role's
responsibilities, an invariant, a message flow — updates this document (and the
charter where the rule is shared) in the same commit. The `consistency-check`
skill is the audit: phase 1 checks these documents against each other, phase 2
checks the agent and skill definitions against them.
