---
by: qa (consistency-check)
---
# The Codex adapter confines runs with the engine's own sandbox

**What's wrong:** every other shipped adapter bypasses approvals and leaves
confinement to the orchestrator. `adapters/codex.toml` instead runs Codex
inside its own `workspace-write` sandbox. That sandbox also cuts network
access, so the adapter has to declare `network = false`.

**Spec (canonical):**
- `docs/architecture.md#invariants`, invariant 5 (lines 84-86): "Every run is
  confined to its worktree plus the directories the orchestrator grants, never
  by the engine's own sandbox".
- `docs/team-charter.md#engines--any-coding-cli-through-an-adapter`
  (lines 152-155): "Confinement is the orchestrator's, never the engine's own
  sandbox: approvals are bypassed inside that boundary so a run never waits on
  a prompt nobody can answer".

**Contradicting side:** `adapters/codex.toml`
- line 13: `command = ["codex", "exec", "--sandbox", "workspace-write", …]`;
- line 4: "`workspace-write` makes the working directory writable";
- line 10: `network = false`.

**Canonical resolution:** the invariant. The adapter bypasses the engine
sandbox and approvals the way the other adapters do, and its `network` value
reflects the result.

**Consequence:** on Codex, items that need ports are refused
(`bin/sdt:1869-1870`; `roles/manager.md` lines 96-98 block them), and any gate
step that needs the network fails inside a run. That makes engines behave
differently, which the "engines are interchangeable" invariant forbids.

**Acceptance criteria:**
- `adapters/codex.toml` uses the Codex CLI's documented
  approvals-and-sandbox bypass in place of `--sandbox workspace-write`.
- Its `network` value matches the new mode.
- It stays `tested = false` until a real run lands.
- Its header comment explains confinement the way `adapters/claude.toml`
  does.
- `tests/test_units.py::test_render_codex` is updated to the new argv.

**Exact files to change:** `adapters/codex.toml`, `tests/test_units.py`.

**Suggested approach:** confirm the flag name with `codex exec --help` on an
installed CLI before changing it. This audit did not run Codex.
