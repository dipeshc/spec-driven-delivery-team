# Exploration and spike promotion (root-owned, outside the pipeline)

Kept separate from `SKILL.md` so the team skill stays focused on running the pipeline.
Exploration is a **root-spawned specialist, not a team member** — speculative
spikes must not pay the pipeline's ceremony on the way out.

## Sequencing

When the Manager reports **DRAINED** and the user has asked for exploration time
(e.g. an overnight window), spawn the `delivery-team:exploration` agent (root-owned,
background, frontier model per the charter's capability gate) and steer its waves
yourself. It works in its own worktree on an `explore/*` branch and never touches
the default branch, so it can even overlap a running team if the user wants both.

## Promotion — through the team, always

When the user picks a spike to keep, file a `P#-promote-<spike>` backlog item
(into the location and under the conventions named in
`<repo>/.delivery-team/profile.md`, **Backlog**) referencing the spike's
branch/tag + SHA and what — if anything — the user wants changed from the spike. A team Developer adapts it onto the current default
branch as one commit; a Reviewer reviews it at production standard; the
Merge-Clerk lands it and the QA guards the merge.

Spikes skip the quality gate on the way out and pay it back at promotion: the
promoting change runs the profile's gate (**full** if it is cross-cutting, plus
any repo-wide invariant guard it triggers) like any other change. **Never
cherry-pick a spike to the default branch yourself.**
