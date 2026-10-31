# Quote the engine's first error line when a run fails before producing a result

**What's wrong:** when an engine process dies before printing a final message,
the orchestrator records the failure as `engine stdout holds no JSON object;
exit code 1` — the event, the ledger note and the ⛔ reason appended to a
blocked item all carry that generic text, and the actual cause (an
authentication error, a missing binary, a quota refusal) is only in the run
log under `.delivery-team/runs/`.

**Evidence:** `bin/sdt`, `RoleRun.result()` builds `RunResult.error` from the
`SdtError` raised by `extract_final_text()` / `parse_result()` and the exit
code only; `Orchestrator.on_developer()` and `Orchestrator.on_manager()` pass
that string into `ask_manager()` and `block()` unchanged. A Gemini CLI run that
failed at sign-in produced a blocked item whose reason said nothing about
authentication.

**Consequence:** the owner reading `blocked/` or the board cannot tell an
engine outage from a model that returned no verdict without opening the log.

**Acceptance criteria:**
- `RunResult.error` for a run that produced no parsable result includes the
  first line of the run log that looks like an error (a line starting with
  `Error`, `error:`, `An unexpected`, `FATAL`, `Traceback`, or containing
  `Error:`), truncated to 200 characters, after the generic description.
- When no such line exists, the error includes the last non-empty log line
  instead.
- `tests/test_units.py` gains a test that feeds `RunResult`-building code a
  log containing an authentication error line and asserts the error string
  contains it; a second case with no error-shaped line asserts the last line
  is used.
- The charter's "Role runs" section says a failed run's reason quotes the
  engine's own error line, so a blocked item explains itself.

**Exact files to change:** `bin/sdt` (`RoleRun.result`), `tests/test_units.py`,
`docs/team-charter.md`.

**Suggested approach:** add a small `first_error_line(text: str) -> str`
helper beside `parse_result()` and call it from `RoleRun.result()` when
building the failure; keep the helper pure so the unit test needs no process.
