---
name: team
description: >
  Run the delivery team over this project's backlog from any coding harness.
  Route each ask to the direct lane (done here, in this session) or the team
  lane (worked by the orchestrator, `sdt run`, which drives Developers, the
  Reviewer, the Merge-Clerk and QA on the configured engine), file backlog
  items, report progress from the ledger, and surface what only the owner can
  clear. Use when the user asks to run the team, work the backlog, check the
  run's status, or invokes /team. Works in any repo that has a
  `.delivery-team/` directory.
---

Steward a delivery run. You — the owner's harness session — stay thin: you
**route by lane, do direct-lane work yourself, start the orchestrator, file
items, report from the ledger, and surface blocks**. You never triage,
implement, review or merge on the team lane: the orchestrator (`sdt`) owns
that loop, running every role as a headless engine process in its own
worktree and keeping its durable state in git and mirroring the run to the progress ledger.

`sdt` is the framework's `bin/sdt`. It is on your PATH when the framework was
installed as a plugin or with `sdt install --bin-dir <dir>`; otherwise call it
by path. `sdt paths` prints where the framework, its charter and its roles live.

## Read these first

1. **`<repo>/.delivery-team/profile.md`** and **`config.toml`** — the only
   places this project's specifics live: gate commands, backlog location,
   engine, limits (config), and the specification source of truth, invariant
   guards, content rules, verification environment (profile). `n/a` genuinely
   means "no such requirement here" — never invent one. **If `.delivery-team/`
   is missing, stop and tell the user to run `sdt init`** and fill both files
   in — guessing the quality gate or the backlog convention wastes a cycle.
2. **The team charter** (`docs/team-charter.md` under the framework root from
   `sdt paths`) — the rules every role obeys: lane routing by risk, role runs,
   scoped writers, verification discipline, backlog conventions, message
   schemas. Read it once so your judgments match the roles' rules.

Throughout this skill, `<repo>`, `<default-branch>` and `<backlog>` are
whatever the config says they are.

## Direct lane — skip the team for low-risk work

Before filing anything, decide **which lane the item belongs in** (charter,
"Route work by risk, not by habit"). This decision happens once, at intake —
the orchestrator does not re-litigate it per item.

**Team lane** (worktree, Developer, independent review, Merge-Clerk — the rest
of this skill): auth/security/crypto, data-model or persistence changes,
cross-package interfaces, cross-surface parity work, or a multi-phase feature.

**Direct lane** (the default for everything else — single-area, small expected
diff, existing test coverage): no orchestrator at all. Do a quick grep/read
pass yourself — no research spike, no backlog file, no worktree. If root cause
is found:

1. implement on a short-lived branch;
2. run the config's **scoped** gate for the area you touched, **plus any
   repo-wide invariant guard your change triggers** (profile, "Repo-wide
   invariant guards") — scoped verification silently skips those;
3. one lightweight self-review pass;
4. `merge --ff-only` into the default branch yourself.

The independent verification and the no-run-active case are defined in the
charter's "Scoped writers to the main working tree" (writer 2).

Escalate mid-flight to a research spike, or to filing a team-lane item, if the
grep-first pass doesn't find root cause, or the item turns out to need a real
design decision, or touches more than it looked like at intake. Escalation is
cheap and expected.

## Filing team-lane items — research when needed

When the user asks for new team-lane work, decide: **does filing a correct item
require investigation that would tie you up?** (unknown repro, unfamiliar
subsystem, external services, comparing design options)

- **No** (the ask is already a well-formed item) → write the item file yourself
  into `<backlog>`, in the charter's item shape, priority in the filename, and
  commit it explicit-path (`docs(backlog): …` or the project's equivalent
  scope).
- **Yes** → dispatch the Researcher role and let the orchestrator file what it
  returns:

  ```
  sdt role researcher --file-items --payload '{"item": "<slug or ask>", "question": "<the question>", "item_text": "<the ask>"}'
  ```

  It investigates for real in a scratch worktree and returns `FILED` (items
  written and committed) or `NO-ITEM` (with why); relay the result to the user.

A running orchestrator picks a new item up on its next tick — no relaunch. A
new-item backlog commit is your sanctioned write to the main working tree
(profile, "Sanctioned direct-write paths"); everything else on this lane lands
through the orchestrator.

Remember the charter's item lifecycle: **an item is done when the landing
commit deletes its item file** — a file that outlives its merged work gets
re-dispatched.

## Running the team

1. **`sdt doctor`** — the engine is installed, its preconditions hold, the
   roles are present. Fix what it reports; an `ERROR` blocks the run.
2. **`sdt run --label "<short run title>"`** — in the background, the way
   your harness runs a long command, or in a terminal the user keeps open. It
   triages the backlog, dispatches, reviews, lands, gates and files until the
   backlog is drained, then prints a `DRAINED` summary and exits; `--watch`
   keeps it polling for new items instead. It refuses to start while another
   run holds the project (`.delivery-team/runs/sdt.pid`): never two
   orchestrators against one tree.
3. **`sdt board`** — open the progress board once per run (the page shows "No
   run is active" until the first ledger write, then live-polls it). The owner
   reopens it with the `board` skill; do not reopen a tab they closed.
4. **Report from the ledger, not from memory:** `sdt status` prints the run
   state — items by stage with assignee, model and time in stage, the agents'
   liveness, recent events, the board path. Give the user that, with the
   landed shas from `git log --no-show-signature --oneline -6 <default-branch>`,
   whenever they ask or whenever you next act; never a bare "it's quiet".

The run's log (stdout) is the authoritative narrative; each role run's prompt,
output and result are kept under `.delivery-team/runs/` for inspection.

## Blocks only the owner can clear

An item the orchestrator moved to `<backlog>/blocked/` carries a ⛔ line
saying why: an owner decision, an environment the run cannot provide, a
condition a role must obey but the work cannot satisfy. **Owner consent has no
channel to a role** (charter, "Blocked on policy — fix the condition, not the
bypass"): a role re-checks conditions itself and never takes a peer's word for
the owner's permission. So:

1. **Take the failing condition to the user in the role's own terms** — the
   check that failed, the exact command and its output, and what would have to
   be true for it to pass. Ask for a repair, not for permission.
2. **When the condition is repaired**, move the item file back out of
   `blocked/` (commit it explicit-path); the orchestrator re-triages it and
   the roles re-run their own checks. Never re-word a block hoping for a
   different answer, and never perform the blocked step yourself on the team
   lane.
3. **If it cannot be repaired, the work stays parked** — item, branch and
   worktree intact on disk; tell the user what only they can do.

A `merge-blocked` event in the run log is the everyday instance (a dirty main
tree colliding with a landing, an unsigned commit): the repair is the owner's.

## Auditing the spec on request — use the role, don't improvise

When the owner asks for a documentation-consistency check, a docs-vs-code
check, or "is the spec still true after all this", run the consistency-check
role rather than hand-writing an audit prompt:

```
sdt role consistency-check --file-items
```

It encodes the two phases (spec-vs-itself, then code-vs-spec), the
docs-are-spec applicability gate, the gate-coverage and parity audits, and the
file-nothing-fix-nothing discipline; the orchestrator also runs it on its own
cadence. Improve the role when a run exposes a gap.

## Exploration and spike promotion

Exploration is an owner-run specialist outside the pipeline, not a team
member. When the user asks for exploration time, run it per its own note:
[exploration-and-promotion.md](exploration-and-promotion.md).
