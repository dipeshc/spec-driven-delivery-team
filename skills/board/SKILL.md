---
name: board
description: >
  Open this project's delivery progress board — the zero-runtime browser page
  that renders a live run's pipeline, agent rail, and event feed from the
  Manager's state ledger. Copies the page into place if it is missing and opens
  it over file://; the page shows "no run active" until a Manager writes state,
  so it is safe to open with no run in flight. Use when the user asks to see,
  open, or reopen the board, dashboard, or progress page, or invokes /board.
  Shell and git only — no server, no runtime, no network.
---

Open the delivery **progress board** on demand. The board is a single
self-contained HTML page (`assets/dashboard.html`, shipped in this plugin) that a
running Manager feeds by writing `state.js` beside it on every reconcile; the
page live-polls that file over `file://` and renders the pipeline columns, the
agent rail, and the event feed. It is a **renderer, never a source of truth** —
deleting it changes nothing about a run.

This skill exists so the owner can reopen the board after closing its tab, or
open it before a run starts to watch the pipeline fill. The team skill's spawn
step already opens it **once per run**; this skill imposes no once-per-run limit,
because an explicit request is the owner asking for it again.

## Steps

1. Resolve the target directory from the project profile. The default is
   `<repo>/.delivery-team/progress/`. If the profile's **Progress board** section
   names a different path, use it; if that section is `n/a`, tell the user the
   board is turned off for this project and stop.

2. Ensure the page exists beside where the Manager writes state, then open it —
   shell only, by platform, tolerating a headless host with nothing to open:

   ```
   mkdir -p "<repo>/.delivery-team/progress"
   [ -f "<repo>/.delivery-team/progress/dashboard.html" ] \
     || cp "${CLAUDE_PLUGIN_ROOT}/assets/dashboard.html" "<repo>/.delivery-team/progress/dashboard.html"
   open    "<repo>/.delivery-team/progress/dashboard.html" 2>/dev/null \
     || xdg-open "<repo>/.delivery-team/progress/dashboard.html" 2>/dev/null \
     || start "" "<repo>/.delivery-team/progress/dashboard.html" 2>/dev/null || true
   ```

3. Tell the user the board's **absolute path** as a clickable `file://` link, so
   a terminal that cannot pop a browser still gives them a way in. If no
   `state.js` sits beside the page (no run is active, or a finished run cleaned
   up), the page renders **"no delivery-team run is active"** and waits — it
   never errors on a missing or partial state file.

The page needs no network and no external assets; it works fully offline from a
plain checkout.
