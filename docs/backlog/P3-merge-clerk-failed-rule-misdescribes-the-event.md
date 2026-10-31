---
by: qa (consistency-check)
---
# The Manager's `MERGE-CLERK-FAILED` rule describes a reason the event never carries, and a `retry` re-implements an approved branch

*Line numbers are at `acc20ec`.*

**What's wrong:** `roles/manager.md` rules on `MERGE-CLERK-FAILED` together
with `MERGE-BLOCKED`, as though its reason named a landability condition
(unsigned commit, trailer, conflict). Under the charter, though,
`MERGE-CLERK-FAILED` escalates a *failed Merge-Clerk run*. It carries the
engine error. And when the Manager answers `retry`, the orchestrator sends the
already-approved item back to a Developer and through review again.
`REVIEWER-FAILED`, the sibling event added in the same commit, goes back to
review instead.

**Spec (canonical):** `docs/team-charter.md#role-runs--how-every-role-executes`
(lines 107-116):
- a run with no block, an unparsable block or an engine failure "is a failed
  run, never read as a verdict";
- "A Developer, Reviewer or Merge-Clerk failure escalates to the Manager as a
  `DECISION-REQUEST` (`DEVELOPER-FAILED`, `REVIEWER-FAILED`,
  `MERGE-CLERK-FAILED`)".

Landability conditions come back from a clerk run that *succeeded*, as
`MERGE-BLOCKED {reason}` (line 603).

**Contradicting side:**
- `roles/manager.md:149-154`: "**`MERGE-BLOCKED` / `MERGE-CLERK-FAILED`**:
  the reason names the condition (unsigned commit, attribution trailer, a
  dirty main tree, a real conflict). A condition the developer can repair
  (amend, rebase by hand) is `retry` with that instruction; a condition only
  the owner can repair is `block` naming it."
- The sibling rule in the same file, `roles/manager.md:142-148`, gives the
  principle that applies: "a failed review says nothing about the branch.
  `retry` once when the error looks transient … the orchestrator sends the
  item back to review, not to a developer."

**Code:**
- `bin/sdt:1761-1769` (`on_merge_clerk`): after `adopt_attempts` failed runs,
  the detail is `{error, log, attempts}`. It has no `reason` and names no
  landability condition.
- `bin/sdt:1551-1558` (`on_manager`): only `REVIEWER-FAILED` sends a `retry`
  or `adopt` back to its stage. A `MERGE-CLERK-FAILED` `retry` takes the
  generic branch. It resets `rounds` to 0, sets `pending` to `RETRY` and
  queues the item for a Developer.

**Verified:** a scratch unit test on `acc20ec` (`orch` fixture,
`adopt_attempts = 2`):
- two failed clerk runs (`error="timeout"`) left the item in `landing` with
  `failures == {"merge-clerk": 2}`;
- the third raised `MERGE-CLERK-FAILED` with detail
  `{"error": "timeout", "log": …, "attempts": 3}`;
- a `DECISION {action: retry}` then left it `queued`, with
  `pending == {"message": "RETRY", "reason": "transient"}` and `rounds == 0`.

**Consequence:** a Manager following its role file looks in the detail for a
condition that isn't there. For a transient clerk failure, a timeout or a
rate limit, it then has two choices. It can `block`, which makes the owner
unblock a branch that was fine. Or it can `retry`, which spends a Developer
run and a full review round on a branch the Reviewer already approved.

**Canonical resolution:** the charter defines `MERGE-CLERK-FAILED` as a failed
run, so the role file must describe it that way. A failed clerk run says
nothing about the approved branch, any more than a failed review does. So it
follows the `REVIEWER-FAILED` rule, and a `retry` re-sends the item to the
Merge-Clerk.

**Acceptance criteria:**
- `roles/manager.md` gives `MERGE-CLERK-FAILED` its own bullet. It is the
  clerk run that died or returned nothing usable after the re-dispatch
  attempts, and the detail names the error, the log and the attempt count.
  `retry` once when the error looks transient, and the orchestrator re-sends
  the item to the Merge-Clerk. A second occurrence, or an error only the
  owner can fix, is `block` naming it. `MERGE-BLOCKED` keeps the
  condition-based rule.
- `bin/sdt` `on_manager`: a `retry` (or `adopt`) on `MERGE-CLERK-FAILED`
  puts the item back in `landing`, with no `pending["landing"]` and its head
  and branch unchanged. The next `dispatch_landing` starts a Merge-Clerk run,
  and no Developer is dispatched.
- `tests/test_units.py` covers that path: after a `MERGE-CLERK-FAILED`
  `retry`, `orch.started` gains a `merge-clerk` run and no `developer` run.
- `uv run pytest -q` passes.

**Exact files to change:** `roles/manager.md`, `bin/sdt` (`on_manager`),
`tests/test_units.py`.

**Suggested approach:** widen the existing `REVIEWER-FAILED` branch in
`on_manager` (`bin/sdt:1551-1554`) into a small map from failure event to the
stage it returns to: `REVIEWER-FAILED` to `review` (re-queued in
`review_batch`), `MERGE-CLERK-FAILED` to `landing`. The doc correction in
`roles/manager.md` is the part the charter decides outright. If the owner
would rather keep the Developer route, that bullet must say so explicitly
instead.
