---
name: board
description: >
  Open this project's delivery progress board — the zero-runtime browser page
  that renders a live run's pipeline, agent rail, and event feed from the
  orchestrator's state ledger. Copies the page into place if it is missing and
  opens it over file://; the page shows "no run active" until the orchestrator
  writes state, so it is safe to open with no run in flight. Use when the user
  asks to see, open, or reopen the board, dashboard, or progress page, or
  invokes /board.
---

Open the delivery **progress board** on demand. The board is a single
self-contained HTML page (`assets/dashboard.html`, shipped with the framework)
that a running orchestrator feeds by writing `state.js` beside it on every
tick; the page live-polls that file over `file://` and renders the pipeline
columns, the agent rail, and the event feed. It is a **renderer, never a source
of truth** — deleting it changes nothing about a run.

This skill exists so the owner can reopen the board after closing its tab, or
open it before a run starts to watch the pipeline fill. The team skill opens it
**once per run**; this skill imposes no once-per-run limit, because an explicit
request is the owner asking for it again.

## Steps

1. Run:

   ```
   sdt board
   ```

   It uses the fixed board directory `<repo>/.delivery-team/progress/` (the
   charter fixes the ledger path, so it is not configurable), copies the page in if it is missing
   (`--refresh` recopies it after a framework update), opens it by platform
   (`open`, `xdg-open`, or `start`; a headless host simply has nothing to
   open), and prints the page's `file://` URL. If `[board] enabled = false`, it
   says the board is off for this project and stops.

2. Give the user that URL as a clickable link, so a terminal that cannot pop a
   browser still gives them a way in. If no `state.js` sits beside the page
   (no run is active, or a finished run was cleaned up), the page renders **"no
   run is active"** and waits — it never errors on a missing or partial state
   file.

The page needs no network and no external assets; it works fully offline from a
plain checkout.
