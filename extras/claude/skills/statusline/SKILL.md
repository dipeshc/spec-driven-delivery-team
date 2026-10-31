---
name: statusline
description: >
  Install (or update, or remove) the delivery-team statusline — the always-on,
  two-line terminal summary of a team run, rendered under every session in this
  project from the orchestrator's state ledger. Copies the shell script to a stable
  user-level path and wires statusLine in ~/.claude/settings.json. If a
  statusline is already configured it never clobbers it: it offers to chain
  (run the existing command, then append the team lines) or to decline, and says
  exactly what it changed. Use when the user asks to install, set up, update, or
  uninstall the team statusline, or invokes /statusline. Shell only — no server,
  no runtime, no network.
---

Install the delivery-team **statusline**: the two-line summary Claude Code shows
under every session, rendered from the orchestrator's `state.js`/`state.json` ledger.
Line one is the aggregate — items done/total with a bar, counts by stage, the
default-branch tip, an ahead-of-origin marker, and run elapsed. Line two is the
one item most worth attention — the item in review and/or blocked, with its
agent, model, and stage-elapsed. Outside a team project (no state file) it prints
nothing, so it is safe to leave installed everywhere. The script is a **renderer,
never a source of truth**.

This is a **user-level** surface: it lives in `~/.claude/settings.json` and
applies to every project you open, silencing itself where no run is active. No
per-project profile change is needed.

## Why a stable path, not the plugin cache

The plugin is installed under a **version-scoped** cache directory whose path
changes every time the plugin updates, so `settings.json` must never point into
it — the next update would leave a dangling command. The installer copies the
script to a stable, version-independent path under the user's home and points
`settings.json` there.

## Install

1. **Copy the script to the stable path.** Resolve `$HOME` to an absolute path
   (settings values are literal — do not rely on `~` expansion when you write
   the file). Copy and mark executable:

   ```
   mkdir -p "$HOME/.claude/delivery-team"
   cp "${CLAUDE_PLUGIN_ROOT}/extras/claude/skills/statusline/statusline.sh" "$HOME/.claude/delivery-team/statusline.sh"
   chmod +x "$HOME/.claude/delivery-team/statusline.sh"
   ```

   Running this step again is how you **update** the script after a plugin
   upgrade — it overwrites the copy in place and touches nothing else.

2. **Read `~/.claude/settings.json`.** If the file does not exist, treat it as
   `{}`. Read it as JSON and inspect its `statusLine` key.

3. **Wire `statusLine`, branching on what is already there.** The team block is:

   ```json
   "statusLine": {
     "type": "command",
     "command": "bash /ABSOLUTE/HOME/.claude/delivery-team/statusline.sh",
     "refreshInterval": 3,
     "padding": 0
   }
   ```

   (`/ABSOLUTE/HOME` is the resolved `$HOME`. `refreshInterval` is in **seconds**
   (minimum 1) — a small value keeps the line's elapsed and staleness fresh
   between ledger writes; the script is cheap (no jq, no git read), so 3 is
   comfortable and stays well under the ~90 s staleness window.)

   - **No `statusLine` yet** → add the team block verbatim. Preserve every other
     key in the file exactly; write it back with the same formatting.

   - **`statusLine` already points at this script** (its `command` already
     contains `delivery-team/statusline.sh`) → it is already installed. Do not
     rewrite it; offer only to refresh the copied script (step 1) and stop.

   - **`statusLine` is some other command** → **do not clobber it.** Present the
     user two choices and act only on their answer:

     - **Chain** (recommended): keep their statusline and append the team lines
       below it. Set `command` to

       ```
       bash /ABSOLUTE/HOME/.claude/delivery-team/statusline.sh --chain '<ORIGINAL COMMAND>'
       ```

       where `<ORIGINAL COMMAND>` is their previous `command` string **verbatim**,
       wrapped in single quotes (escape any embedded single quote as `'\''`). The
       script runs that command first with the same stdin and prints its output,
       then appends the team lines — so their statusline is untouched and the team
       lines sit beneath it. Leave their `type`, `refreshInterval`, and any other
       `statusLine` keys as they were.

     - **Decline**: change nothing. Tell them the exact block they could add by
       hand if they change their mind.

4. **State exactly what changed.** Report the file you wrote
   (`~/.claude/settings.json`), the previous `statusLine.command` (or "none"),
   and the new one. If you declined or only refreshed the script, say so. Never
   report a change you did not make.

The line renders nothing until a run is active and the orchestrator has written state beside
the project, so installing before a run is safe — the terminal simply shows your
existing statusline (or nothing) until a run begins.

## Uninstall

1. In `~/.claude/settings.json`, look at `statusLine.command`.
   - **Bare team command** (`bash …/statusline.sh`, no `--chain`) → remove the
     whole `statusLine` key.
   - **Chained team command** (`bash …/statusline.sh --chain '<ORIGINAL>'`) →
     restore the user's prior statusline: set `command` back to `<ORIGINAL>`, the
     single-quoted string after `--chain` with its `'\''` escapes unwound.
   Preserve every other key in the file.
2. Optionally delete the copied script and its directory:
   `rm -f "$HOME/.claude/delivery-team/statusline.sh"` (and `rmdir` the directory
   if empty).
3. Report exactly what you removed or restored.
