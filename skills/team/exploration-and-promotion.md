# Exploration and spike promotion (owner-run, outside the pipeline)

Kept separate from `SKILL.md` so the team skill stays focused on running the
pipeline. Exploration is an **owner-run specialist, not a team member** —
speculative spikes must not pay the pipeline's ceremony on the way out.

## Sequencing

When the run reports **DRAINED** and the user has asked for exploration time
(e.g. an overnight window), run the exploration role on the configured engine:

```
sdt role exploration --payload '{"themes": ["..."], "constraints": ["..."]}'
```

It works in its own scratch worktree on an `explore/*` branch and never
touches the default branch, so it can even overlap a running team if the user
wants both. Relay its `EXPLORATION-REPORT` — one line per spike, what it
declined and why, the state of the exploration log — to the user.

## Promotion — through the team, always

When the user picks a spike to keep, file a `P#-promote-<spike>` backlog item
(into the backlog location, under the charter's item shape) referencing the
spike's branch/tag + sha and what — if anything — the user wants changed from
the spike. A team Developer adapts it onto the current default branch as one
commit; the Reviewer reviews it at production standard; the Merge-Clerk judges
it landable, the orchestrator lands it and runs the full gate on the result.

Spikes skip the quality gate on the way out and pay it back at promotion: the
promoting change runs the gate (**full** if it is cross-cutting, plus any
repo-wide invariant guard it triggers) like any other change. **Never
cherry-pick a spike to the default branch yourself.**
