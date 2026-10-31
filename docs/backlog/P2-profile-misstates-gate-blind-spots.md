---
by: qa (consistency-check)
---
# The profile says everything the gate skips is prose, but the gate also skips three executable files

*Line numbers are at `547befb`.*

**What's wrong:** `.delivery-team/profile.md` makes three false claims:
- the repo outside `bin/sdt` is Markdown;
- what the gate cannot exercise is prose;
- the reviewer's reading is that prose's verification.

The gate also never runs the statusline shell script, the dashboard's
JavaScript, or the sweep workflow's JavaScript, and the profile names none of
them. The profile's Layout also omits `assets/`.

**Spec (canonical):**
- `roles/consistency-check.md`, Phase 3 (lines 126-130): compare what the
  gate's commands "actually compile, run, and boot against the profile's
  Quality gate claims, including its **Not covered** list … green means those
  commands passed, never that the project works."
- `docs/profile.template.md#quality-gate` (lines 32-35): Not covered is "what
  even the full gate does not compile, boot, or exercise … roles must not
  mistake it for broader verification."

**Contradicting side (`.delivery-team/profile.md`):**
- Line 14: "The rest of the repo is Markdown."
- Lines 31-37 (Quality gate → Not covered): "the role prompts, skills,
  adapters and docs are prose, so the gate (ruff, mypy and pytest over
  `bin/sdt` and `tests/`) cannot exercise them; the reviewer's reading … IS
  their verification".
- Lines 15-27 (Repo → Layout): no `assets/` entry.

**What the gate actually covers:**
- `config.toml` `[gate] full` runs `ruff format --check bin/sdt tests`,
  `ruff check bin/sdt tests`, `mypy` (`pyproject.toml`
  `files = ["bin/sdt", "tests"]`) and `pytest -q`.
- The orchestrator's gate log for `5c1e96c`
  (`.delivery-team/runs/qa-gate-5c1e96c8.log`) shows 5 files formatted, 5
  source files type-checked and 46 tests passed.
- No test runs any of these:
  - `extras/claude/skills/statusline/statusline.sh` (POSIX shell;
    `git grep statusline -- tests` finds nothing);
  - the roughly 770 lines of JavaScript in `assets/dashboard.html`
    (lines 442-1209; `tests/test_e2e.py:130` only asserts the page is
    copied);
  - `extras/claude/workflows/consistency-sweep.js`.

The profile never claimed these files were covered, so this is not coverage
that drifted (the Phase 3 P1 case). It is a blind-spot list that misstates
what the gate skips.

**Consequence:**
- A reviewer reads "Not covered: prose" and takes a green gate to mean every
  executable file passed.
- The statusline defect in `P2-statusline-miscounts-ledger-history` shipped
  green for exactly this reason.
- Triage and the Reviewer use this list to judge what a change's verification
  proves.

**Acceptance criteria:**
- Not covered names each executable file the gate does not run, and how it is
  verified instead:
  - the statusline script, until that item adds a test;
  - the dashboard page;
  - the sweep workflow, while it exists.
- Line 14 no longer says the rest of the repo is Markdown.
- Layout lists `assets/` (the progress board page).
- There is no test surface: this is profile prose.

**Exact files to change:** `.delivery-team/profile.md`.

**Suggested approach:** add a short list beside the existing Not covered
sentence. `P3-sdt-sweep-replaces-the-claude-workflow` (held) edits the same
Layout bullet to drop the workflow, so whichever lands second rebases.
