---
name: consistency-check
description: >
  Run the two-phase specification audit on demand: the spec against itself
  (contradictions, terminology drift, broken links and anchors, decision-record
  coherence, residue of earlier versions), then the code against the spec
  (docs are truth; every confirmed delta is a code bug), then the gate's own
  coverage and cross-surface parity. Every finding is filed as a backlog item;
  nothing is fixed in place. Use whenever a docs-vs-docs or docs-vs-code audit
  is wanted, ad hoc or against a recent change; the orchestrator also runs it
  on its own cadence.
---

Run the consistency audit through the orchestrator, which dispatches the
`consistency-check` role (`roles/consistency-check.md` under the framework
root — that file owns the method) on the configured engine in a scratch
worktree and files what it returns:

```
sdt role consistency-check --file-items
```

Optionally narrow the pass with a payload, which the role treats as its audit
range:

```
sdt role consistency-check --file-items --payload '{"range": "<sha>..<default-branch>", "focus": "docs/architecture.md"}'
```

The role keeps its audit marker and dismissed judgment calls in its notes file
(`.delivery-team/notes/consistency-check.md`), so each pass is incremental
unless the payload says otherwise. The command prints the role's `FINDINGS`
result — the range audited, anything left unverified, and the items filed —
which you relay to the user. **You fix nothing and file nothing yourself**: a
finding becomes a backlog item that a Developer lands through review, like any
other change.

Applicability (docs-as-spec or not, no docs root) is the role's own gate, read
from the project's profile; where the audit does not apply it says so and
files nothing.
