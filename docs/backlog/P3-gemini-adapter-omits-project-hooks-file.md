---
by: qa (consistency-check)
---
# The Gemini adapter does not declare the project hooks file Gemini CLI runs

*Line numbers are at `a5426fb`.*

**What's wrong:** Gemini CLI runs the hooks that a project's
`.gemini/settings.json` declares, and the adapter's `--skip-trust` flag is
what makes it load that file. `adapters/gemini.toml` sets no
`project_hooks_file`, so `sdt doctor` warns about Claude Code's project hooks
but never about Gemini's.

**Spec (canonical):**
- `docs/architecture.md#components` (line 36): an adapter says how to run one
  coding CLI headless, including "which project file declares hooks it runs
  inside every run".
- `adapters/claude.toml:10-12` is the reference use: "Claude Code runs the
  hooks this project settings file declares inside every headless run;
  `sdt doctor` warns when it declares any."

**Code (the delta):**
- `adapters/gemini.toml:8-13`: no `project_hooks_file` key. Line 13 passes
  `--skip-trust`.
- `bin/sdt:352`: `load_adapter` defaults the field to `""`.
- `bin/sdt:1988-1997`: `engine_checks` warns only when
  `adapter.project_hooks_file` is set.

**Engine behaviour.** This comes from the installed CLI's own docs
(gemini-cli 0.46.0, `libexec/lib/node_modules/@google/gemini-cli/bundle/docs/`).
This audit did not run Gemini live.
- `hooks/index.md:92-97`: "Hooks are configured in `settings.json`", and the
  first layer is "**Project settings**: `.gemini/settings.json` in the current
  directory."
- `hooks/best-practices.md:411-421`: when a project defines hooks in
  `.gemini/settings.json`, an unseen hook gets a warning and then
  "**Execution**: The hook is executed".
- `cli/trusted-folders.md:77-78`: an untrusted workspace does not load
  `.gemini/settings.json`.
- `cli/trusted-folders.md:105-118`: in a headless run, `--skip-trust` trusts
  the workspace for the session.
- `cli/settings.md:195`: `hooksConfig.enabled` defaults to `true`.
- `hooks/reference.md:255`: hooks have defined non-interactive behaviour.

**Evidence (run by this audit):** a scratch git repo had both
`.gemini/settings.json` and `.claude/settings.json` declaring a `hooks`
table, and `sdt doctor` ran from the `a5426fb` snapshot.
- `[engine] default = "gemini"`: only the untested-adapter and missing-model
  warnings, then `doctor: ready`.
- `[engine] default = "claude"`: `WARN  engine claude: project
  .claude/settings.json declares hooks; they run inside every headless role
  run`.

**Consequence:** on Gemini, a committed project hook fires inside every role
run and the owner gets no warning. A `BeforeTool` hook can block a role's
tool calls, and an `AfterAgent` hook can force a retry. Either one changes
role runs with nothing in doctor's output to explain it. The shipped adapters
also fall short of the shape the architecture row describes.

**Acceptance criteria:**
- `adapters/gemini.toml` declares
  `project_hooks_file = ".gemini/settings.json"`. A comment in the style of
  `adapters/claude.toml:10-11` says Gemini CLI runs the hooks that file
  declares once `--skip-trust` trusts the workspace, and that `sdt doctor`
  warns when it declares any.
- `tests/test_units.py::test_shipped_preconditions_are_adapter_fields`
  asserts the Gemini value.
- `sdt doctor` in the scratch case above, with `default = "gemini"`, prints
  `engine gemini: project .gemini/settings.json declares hooks; they run
  inside every headless role run`.
- `tested = false` is unchanged.

**Exact files to change:** `adapters/gemini.toml`, `tests/test_units.py`.

**Suggested approach:** one key and one comment. While there, check whether
the Cursor, Copilot, OpenCode and agy CLI references document project-level
hooks. Give an adapter the same field only where its CLI's own reference
documents it. This audit could verify none of the four: three are not
installed, and `agy --help` names no hooks.
