---
by: qa (consistency-check)
---
# `sdt role researcher --file-items` reports a `FILED` that filed nothing as a success

*Line numbers are at `dab25e0`.*

**What's wrong:** on the on-demand path, a Researcher `FILED` whose every filename `file_items` skips is printed as `FILED` with `"filed": []`, and `sdt role` exits 0. The charter now calls that result a failed run, never read as a verdict, and `sdt run` treats it as one since bc5bbc3. `sdt role` treats it as a success.

**Spec (canonical):**
- `docs/team-charter.md#role-runs--how-every-role-executes`, "The result." (lines 107-110): "a run with no block, an unparsable block, or an engine failure is a failed run, never read as a verdict, and so is a Researcher `FILED` that files no item." This is the owning, normative definition of a failed run, and it is not limited to `sdt run`.
- `roles/researcher.md#what-you-return` (lines 71-73): "A `FILED` whose every filename the orchestrator skips (the charter's message table names the ones it writes) files nothing, retires nothing, and is a failed run."
- `skills/team/SKILL.md#filing-team-lane-items--research-when-needed` (lines 82-90) has the owner's session run `sdt role researcher --file-items ...` and says: "It investigates for real in a scratch worktree and returns `FILED` (items written and committed) or `NO-ITEM` (with why); relay the result to the user."

**Code (the delta):**
- `bin/sdt:2758-2760` (`cmd_role`): a failed run prints `{"message": "RUN-FAILED", "error", "log"}` and returns 1. That is how the on-demand path reports a failed run.
- `bin/sdt:2763-2767`: with `--file-items`, `file_items` runs, `res.payload["filed"]` is set to the names written (possibly `[]`), and the payload is printed with `return 0`. Nothing checks for a `FILED` that filed nothing. The same holds when `items` is missing or not a list (line 2763 skips filing entirely).
- By contrast, `bin/sdt:2184-2190` (`on_researcher`, the `sdt run` path) routes `if not written` to `research_failed` with the reason `FILED filed no item (filenames skipped: ...)`.

**Verified (run by this audit):** in a scratch copy of `dab25e0`, a unit test (`make_project` from tests/test_units.py) monkeypatched `sdt.Project.start_run` to return a finished run whose result is `RunResult(True, payload={"message": "FILED", "items": [{"filename": "docs/backlog/P2-sharpened.md", "body": "# Sharpened\n"}]})`. It then called `sdt.cmd_role` with `name="researcher"`, `file_items=True`, `cwd=<repo>`. Results:
- stdout read `skipping item with bad filename 'docs/backlog/P2-sharpened.md'`;
- the printed JSON was `{"message": "FILED", "items": [...], "filed": []}`;
- `cmd_role` returned 0;
- no file was written to the backlog.

**Canonical resolution:** the charter's result paragraph owns the failed-run definition, and the Researcher role restates it. On the on-demand path, a failed run is reported as `RUN-FAILED` with exit 1, so a Researcher `FILED` that files nothing under `--file-items` must be reported that way too. Without `--file-items` the owner asked for no filing, so a `FILED` stays a result there.

**Consequence:** the owner's session follows `skills/team/SKILL.md`. It reads `FILED` with exit 0 and relays that the researched item was "written and committed", but the backlog holds nothing. The researched text survives only in the printed payload and the run log.

**Acceptance criteria:**
- `sdt role researcher --file-items` whose result is `FILED` and files no item prints `{"message": "RUN-FAILED", "error": ..., "log": ...}` and exits 1. The error names the skipped filenames (or says none were returned), like `on_researcher`'s reason.
- A `FILED` that files at least one item, a `NO-ITEM`, and any `sdt role` run without `--file-items` behave as they do today.
- A new unit test in `tests/test_units.py` drives `cmd_role` with a stubbed `Project.start_run` and covers: a `FILED` whose only filename is skipped → exit 1 and `RUN-FAILED`; a `FILED` with one valid filename → exit 0 and the file written. The first case fails against `dab25e0`.

**Exact files to change:** `bin/sdt` (`cmd_role`), `tests/test_units.py`.

**Suggested approach:**
- In `cmd_role`, after `file_items`, when `args.name == "researcher"` and `res.payload.get("message") == "FILED"` and nothing was filed (including a missing or non-list `items`), print the existing `RUN-FAILED` shape with `log` set to `res.log_path` and return 1.
- Build the skipped-filenames text the same way `on_researcher` does (`bin/sdt:2188`), or factor out a small helper both paths call.
- The scratch test pattern: `monkeypatch.chdir(project.root)`; `monkeypatch.setattr(sdt.Project, "start_run", lambda self, name, payload, **kw: SimpleNamespace(poll=lambda: True, result=lambda: sdt.RunResult(True, payload=...)))`; call `sdt.cmd_role(argparse.Namespace(adapter_dir=[], payload="{...}", name="researcher", cwd=str(project.root), tier=None, engine=None, file_items=True))`.
