---
by: qa (consistency-check)
---
# A role-returned item filename can escape the backlog and end the run, and a Researcher `FILED` that files nothing still deletes the originating item

*Line numbers are at `c0e73ce`.*

**What's wrong:** two defects in how the orchestrator applies the `{filename, body}` pairs a role returns. Both sit in `file_items` and its Researcher caller.

1. **The name check misses a leading slash and a NUL.** `file_items` strips slashes before it tests for one, but joins the unstripped name. So `/P2-x.md` is written at `/P2-x.md`, outside the backlog and outside the repository. A name holding a NUL raises `ValueError`. Neither error is an `SdtError`, so it escapes the result handler and ends `sdt run` with a traceback.
2. **A `FILED` that files nothing still retires the rough ask.** The Researcher can return `FILED` with every item skipped by the check, for example `docs/backlog/P2-x.md` (a path, not a name). `on_researcher` still retires the originating item, with the subject "superseded by researched item(s)" and the body "Filed: nothing". The rough ask leaves the backlog, and nothing replaces it.

**Spec (canonical):**
- `docs/team-charter.md#backlog-conventions` (line 412): "Per-item files live where `config.toml` `[backlog] dir` says".
- `docs/team-charter.md#scoped-writers-to-the-main-working-tree`, writer 3 (lines 295-299): the orchestrator's housekeeping writes "backlog item files returned by the QA, Researcher or consistency check as `{filename, body}` pairs", and does the "deleting a researched item". No writer is sanctioned outside the repository.
- `docs/team-charter.md#engines--any-coding-cli-through-an-adapter` (line 176): "Engine output is an **untrusted contributor diff**". A returned filename is engine output.
- `roles/researcher.md#what-you-return`:
  - line 44: `FILED` is "One item file per real piece of work";
  - lines 68-70: "The orchestrator writes and commits the files and retires the originating item". The retirement follows the write.
  - Line 15: the Researcher exists to "hand back an item a capable-but-cheaper developer can action cold".
- `docs/team-charter.md#role-runs--how-every-role-executes` (lines 112-119): every failed run is re-dispatched up to `adopt_attempts` times per item, then a Researcher failure blocks the affected item with the error as the reason.

**Code (the delta):**
- `bin/sdt:1093`: the check is `"/" in name.strip("/").replace("blocked/", "")`. Stripping first lets `/P2-x.md`, `//P2-x.md` and `/blocked/P2-x.md` through.
- `bin/sdt:1096`: `path = self.backlog / name`. Joining an absolute name discards the backlog, so `path` is `/P2-x.md`. Lines 1097-1099 create its parent, write it and `git add` it.
- Nothing rejects a NUL, and a JSON string can carry one as an escape. `write_text` then raises `ValueError: embedded null byte`.
- Every filing path shares the check:
  - `on_qa` (`bin/sdt:2093`);
  - `on_consistency` (`:2143`);
  - `on_researcher` (`:2169`);
  - `sdt sweep` (`:2441`);
  - `sdt role --file-items` (`:2734`).
- Nothing catches these errors:
  - `housekeep` (`bin/sdt:1619-1624`) runs `fn` directly when no landing is in flight.
  - Only `flush_housekeeping` catches, and only `SdtError` (`:1631-1634`).
  - `Orchestrator.run` catches only `KeyboardInterrupt` (`:2247`), and `main` catches only `SdtError` (`:2802`).
  - So an `OSError` or `ValueError` from `file_items` ends the run.
  - Where the filesystem root is writable (a container running as root), the stray write succeeds. The `git add` of a path outside the repository then raises `SdtError`, which also ends the run.
- Engine runs and the gate start in their own sessions (`bin/sdt:631`, `:775`). The crash path kills neither, so they are left running with no reader.
- `bin/sdt:2169-2184` (`on_researcher`, `apply()`): when `file_items` returns no names, `filed` is empty, but `retire_items` still runs on every originating path. The skip itself goes only to the orchestrator's stdout (`log()`, `:1094`), not to the event feed.

**Verified (run by this audit):** in a scratch copy of `c0e73ce`, with tests built on `triage_orchestrator` (tests/test_units.py). A `Path.write_text` spy refused every write outside the test's tmp dir.
- `file_items([{"filename": "/P2-escape.md", …}])` tried to write `/P2-escape.md`, and so did `//P2-escape.md`.
- `/blocked/P2-escape.md` tried to create `/blocked`: `OSError: [Errno 30] Read-only file system`.
- A name holding `chr(0)` raised `ValueError: embedded null byte`.
- An item triaged to `research` was then fed `on_run_done` with `FILED {items: [{filename: "/P2-sharpened.md"}]}`. The write went to `/P2-sharpened.md`, and the `PermissionError` escaped `on_run_done`. It is not an `SdtError`.
- The same item fed `FILED {items: [{filename: "docs/backlog/P2-sharpened.md"}]}`:
  - stdout read `skipping item with bad filename 'docs/backlog/P2-sharpened.md'`;
  - the log read `chore(backlog): retire P2-rough-ask — superseded by researched item(s)`, with body `Filed: nothing`;
  - the backlog was empty afterwards.
- The full gate is green at `c0e73ce` (94 passed), so no test covers these paths.

**Canonical resolution:**
- From the backlog conventions and writer 3: a returned filename names a file directly in the backlog dir or its `blocked/`. Anything else is skipped, as the existing check intends. A bad name is never fatal to the run.
- From the Researcher role: the originating item is retired as superseded only by an item that was actually filed. A `FILED` that files nothing has not delivered its result. It follows the charter's failed-run policy for the Researcher: re-dispatch, then block the item with a reason naming the skipped filenames. The rough ask stays in the backlog throughout.

**Consequence:**
- One malformed name from any engine ends `sdt run` mid-pipeline:
  - the role's result is never filed;
  - live engine runs and any running gate are left with no orchestrator to read them;
  - on a writable root, the orchestrator first writes outside the repository.
- A Researcher's sharpened item is lost. The rough ask it should replace is deleted under a commit subject saying it was superseded. Only git history and the run's log under `.delivery-team/runs/` keep either.

**Acceptance criteria:**
- `file_items` writes only directly inside the backlog dir or its `blocked/`. A name with a leading slash, a `..` segment or a NUL is never written outside it. It is either normalised to a plain name inside the backlog or skipped with the existing `skipping item with bad filename` log line.
- No filename makes a result handler raise. `sdt run` keeps running after a role returns one.
- A Researcher `FILED` that files no item retires nothing. It is re-dispatched up to `adopt_attempts` times, then its item is blocked with a reason naming the skipped filenames.
- A `FILED` that files at least one item behaves as it does today, including the rewritten-in-place case. `test_research_refiled_under_its_own_filename_survives_and_is_retriaged` and `test_research_retired_regression_is_closed_but_never_done` still pass.
- New unit tests in `tests/test_units.py`, each failing against `c0e73ce`:
  - `/P2-x.md` and a name holding a NUL write nothing outside the backlog and raise nothing;
  - a Researcher `FILED` whose only item is skipped leaves the originating file in place and is re-dispatched.

**Exact files to change:** `bin/sdt` (`file_items`, `on_researcher`), `tests/test_units.py`.

**Suggested approach:**
- In `file_items`, strip the name once, before both the check and the join. The check's own `strip("/")` suggests a leading slash was meant to be tolerated. Also reject `"\0" in name`.
- As a backstop, skip any `path` whose resolved parent is neither the resolved backlog nor its `blocked/`.
- In `on_researcher`'s `apply()`, when `message == "FILED"` and nothing was written, skip the retirement. Route the item through the branch that handles an unexpected message instead (`retry_due`, re-dispatch, then `block`). Factor that branch out so both paths share it.
