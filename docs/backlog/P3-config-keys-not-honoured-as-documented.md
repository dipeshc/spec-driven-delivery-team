---
by: qa (consistency-check)
---
# Three `config.toml` keys do not behave as the template documents

**What's wrong:** `docs/config.template.toml` is "every key `bin/sdt`
consumes, with its default" (`docs/architecture.md#document-roles`, line 27).
Three keys don't do what it says.

1. **`[limits] reviewers`.**
   - Template (lines 50-51): "Reviewer instances; each gets its own
     persistent worktree reviewer-<n>."
   - Code: `bin/sdt:197` parses it, and nothing reads `cfg.reviewers`.
     `dispatch_reviews()` (`bin/sdt:1460-1468`) always uses the single
     `reviewer-1` and dispatches nothing while any reviewer run is live.
2. **`[limits] review_rounds`.**
   - Template (line 52): "CHANGES-REQUESTED rounds an item may take before
     triage decides its fate."
   - Code: a Reviewer `REBASE-REQUIRED` also counts (`bin/sdt:1531-1535`), and
     so does a Merge-Clerk `REBASE-REQUIRED` (`bin/sdt:1611-1612`). A
     fast-moving base alone can trigger `REVIEW-ROUNDS-EXCEEDED`.
3. **`[repo] install`.**
   - Template (lines 14-15): "Command run once in each freshly created
     worktree (and again in a persistent worktree when `lockfile` changes)."
   - Code (`bin/sdt:818-823`): with `lockfile` empty, `digest` is `""`, so the
     skip condition (`… and digest`) is false. The install then runs on every
     `reset_detached()`: every review batch, landing and gate run.

**Canonical resolution:** the template is the spec for these keys, so the
code must honour them.

**Consequence:**
- A project that sets `reviewers = 2` gets serial review.
- Items on a busy base reach the Manager as "review rounds exceeded" without
  a single review objection.
- A project with an install command and no lockfile pays a full install on
  every persistent-worktree run.

**Acceptance criteria:**
- Up to `reviewers` review batches run concurrently, each in its own
  `reviewer-<n>` worktree.
- Only `CHANGES-REQUESTED` verdicts increment the counter compared with
  `review_rounds`.
- With `lockfile` empty, a persistent worktree runs `install` only when it is
  created.
- `tests/test_units.py` covers the round counting and the install skip.
- `tests/test_e2e.py` runs with `reviewers = 2` and asserts that two reviewer
  worktrees were used.

**Exact files to change:** `bin/sdt` (`dispatch_reviews`, `on_reviewer`,
`on_merge_clerk`, `install_in`), `tests/test_units.py`, `tests/test_e2e.py`.

**Suggested approach:** track live reviewer runs by worktree name, and give
each new batch the first free `reviewer-<n>`.
