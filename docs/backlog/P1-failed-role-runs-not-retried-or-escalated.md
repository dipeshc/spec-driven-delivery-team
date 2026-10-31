---
by: qa (consistency-check)
---
# Failed role runs are read as outcomes instead of being re-dispatched or escalated

**What's wrong:** only the Developer path handles a failed run the way the
charter requires. Elsewhere:
- a failed triage run dispatches every new item;
- a failed Reviewer run is retried forever;
- the Merge-Clerk's retry bound ignores `adopt_attempts`;
- a failed QA run stops regression filing for that failure for the rest of
  the run;
- a failed Researcher run leaves its item marked blocked in memory, but the
  file is never moved;
- a `QA-BLOCKED` result is reported as "regression filed: nothing filed", and
  its reason is dropped.

**Spec (canonical):** `docs/team-charter.md#role-runs--how-every-role-executes`
- lines 107-110: "a run with no block, an unparsable block, or an engine
  failure is a failed run, re-dispatched or escalated by the orchestrator,
  never read as a verdict."
- lines 122-127: "The orchestrator kills a run that exceeds either and
  re-dispatches it with `adopt: true`, bounded by `adopt_attempts`, after
  which triage decides. … A Reviewer batch that times out is re-dispatched
  whole; a timeout is never a verdict."
- `#blocked-on-policy--fix-the-condition-not-the-bypass` (lines 180-187,
  208-212): `QA-BLOCKED` names the failing condition, and "The block stays
  visible until the owner clears it at source".

**Code (the defect):**
- **Triage.** `bin/sdt:1372-1375`: on a failed triage run, the orchestrator
  calls `apply_triage({"items": []}, fresh)`. `bin/sdt:1252-1263` then queues
  every fresh item as "triaged by default": tier `mid`, no `ports`, no guards,
  no governing docs. Verified: after a failed triage, `P1-needs-owner` was
  `queued`, tier `mid`, `ports` False, so it was dispatchable.
- **Reviewer.** `bin/sdt:1507-1510` re-queues the batch on every failure, with
  no counter and no escalation.
- **Merge-Clerk.** `bin/sdt:1578-1582` bounds retries with a hard-coded `3`,
  not `adopt_attempts`.
- **QA run fails.** `bin/sdt:1651` reserves the failure signature
  (`open_regressions[signature] = ""`) before dispatch. `bin/sdt:1674-1677`
  returns on a failed QA run without releasing it. `bin/sdt:1663-1669` treats
  `""` as open, so `bin/sdt:1648-1650` skips every later red tip with the
  same failures as "its regression item is already in flight". Verified:
  after one failed QA run, the next red tip started no QA run, though nothing
  had been filed.
- **QA-BLOCKED.** `bin/sdt:1678-1704` handles only `ENVIRONMENT` specially.
  Any other message is treated as `REGRESSION` with no items, so `qa_state`
  becomes "regression filed: nothing filed" and the `reason` is discarded.
- **Researcher.** `bin/sdt:1734-1737` logs the failure and returns. The item
  stays `blocked` in memory (`bin/sdt:1220`) while its file stays in the
  backlog root.

**Consequence:**
- An engine failure at triage dispatches, at the wrong tier, items the Manager
  would have blocked or that need exclusive resources.
- A persistently failing reviewer engine burns frontier runs indefinitely.
- One failed QA run silently disables regression detection for that failure
  for the rest of the run.
- The owner never sees a QA block or a failed research run as a block.

**Acceptance criteria:**
- Every role handler routes a failed run through one policy: re-dispatch up
  to `adopt_attempts`, then escalate.
  - Developer and Merge-Clerk escalate through their existing
    `DECISION-REQUEST` events.
  - A Reviewer escalates through a new `REVIEWER-FAILED` event.
  - Triage, QA and Researcher failures, which have no Manager ruling to fall
    back on, leave a visible on-disk outcome: the affected item(s) are blocked
    with the engine error as the ⛔ reason, or the gate state stays red with
    the error.
- A failed triage run never dispatches an item.
- A failed or blocked QA run releases its signature reservation, and the QA
  `reason` appears in `qa_state` and in the event.
- `docs/team-charter.md` adds `REVIEWER-FAILED` to the `DECISION-REQUEST`
  event list, and `roles/manager.md` says how to rule on it.
- `tests/test_units.py` or `tests/test_e2e.py` covers each path:
  - a failed triage run;
  - a reviewer run that keeps failing;
  - a failed QA run followed by a second red with the same failure (QA
    dispatched again);
  - a `QA-BLOCKED` result (reason surfaced);
  - a failed Researcher run.

**Exact files to change:** `bin/sdt` (`on_manager`, `on_reviewer`,
`on_merge_clerk`, `run_qa_gate`, `on_qa`, `on_researcher`),
`docs/team-charter.md` (message table), `roles/manager.md`,
`tests/fake_engine.py`, `tests/test_e2e.py` and/or `tests/test_units.py`.

**Suggested approach:** generalise the existing `it.adoptions` /
`adopt_attempts` logic in `on_developer` (`bin/sdt:1427-1436`) into one small
helper that either re-queues or escalates. Keep the attempt counter per item,
or per tip for QA.
