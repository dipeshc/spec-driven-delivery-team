---
by: qa (consistency-check)
---
# `sdt role researcher` dispatches `RESEARCHER-REQUEST`, a message the charter does not define

*Line numbers are at `547befb`.*

**What's wrong:** `cmd_role` gives every role without a special case the
dispatch message `<NAME>-REQUEST`. The researcher's message is
`RESEARCH-REQUEST`, so the on-demand path documented in
`skills/team/SKILL.md` sends `RESEARCHER-REQUEST`.

**Spec (canonical):**
- `docs/team-charter.md#message-schemas--the-canonical-payload-table`,
  line 598: "Orchestrator → Researcher | `RESEARCH-REQUEST` |
  `{item, question, item_text}`".
- The same section, line 574: "Every message conforms to one of these
  shapes."
- `roles/researcher.md#your-dispatch`, line 26:
  "`RESEARCH-REQUEST {item, question, item_text}`".

**Contradicting side:**
- `bin/sdt:2155-2159` special-cases only `consistency-check`. Every other role
  gets `payload.setdefault("message", f"{args.name.upper()}-REQUEST")`.
- `skills/team/SKILL.md:87` documents
  `sdt role researcher --file-items --payload '{"item": …, "question": …, "item_text": …}'`,
  a payload with no `message` key.
- The pipeline's own dispatch is correct (`bin/sdt:1285`).

**Evidence (run by this audit):** on the stub engine, in a scratch repo at
`5c1e96c` (this code is unchanged at `547befb`), this audit ran
`sdt role researcher --payload '{"item": "some ask", "question": "q?", "item_text": "the ask"}'`.
The prompt's Dispatch block ended `"message": "RESEARCHER-REQUEST"`. The
exploration (`EXPLORATION-REQUEST`) and ui-inspector
(`UI-INSPECTOR-REQUEST`) defaults do match the table.

**Consequence:**
- The research path the owner's session is told to use hands the role a
  message the charter does not define, and a careful run may treat it as off
  contract.
- It is the same class of defect that `bf94b5b` fixed, for `RUN-CONSISTENCY`
  only.

**Acceptance criteria:**
- `sdt role researcher` sends `RESEARCH-REQUEST` when the caller's payload
  names no message.
- One map in `cmd_role` gives every role in the charter's table its dispatch
  message. The `<NAME>-REQUEST` fallback applies only to roles absent from the
  table.
- `tests/test_e2e.py` runs `sdt role researcher` on the stub and asserts the
  dispatched message is `RESEARCH-REQUEST`.

**Exact files to change:**
- `bin/sdt` (`cmd_role`).
- `tests/test_e2e.py`.
- `tests/fake_engine.py`, if the stub must echo the message.

**Suggested approach:** add a module-level `DISPATCH_MESSAGES` dict beside
`ROLE_TIERS`:
- `researcher` → `RESEARCH-REQUEST`;
- `consistency-check` → `RUN-CONSISTENCY`, plus its `tip`;
- `exploration` → `EXPLORATION-REQUEST`;
- `ui-inspector` → `UI-INSPECTOR-REQUEST`.
