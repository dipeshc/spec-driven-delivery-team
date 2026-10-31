export const meta = {
  name: 'consistency-sweep',
  description: 'Full parallel spec audit: fan out the consistency-check classes, adversarially verify every finding, file the survivors as backlog items',
  whenToUse: 'A whole-spec audit on demand. The consistency-check role remains the incremental path the orchestrator runs on its cadence; this sweeps everything in parallel and refutes each finding before filing.',
  phases: [
    { title: 'Map', detail: 'applicability gate and file inventory' },
    { title: 'Audit', detail: 'one agent per finding class' },
    { title: 'Verify', detail: 'independent skeptic per finding' },
    { title: 'File', detail: 'serialized filing of survivors' },
  ],
}

const MAP = {
  type: 'object',
  required: ['applicable', 'reason', 'docsAreSpec', 'docsRoot', 'files', 'skillPath'],
  properties: {
    applicable: { type: 'boolean' },
    reason: { type: 'string' },
    docsAreSpec: { type: 'boolean' },
    docsRoot: { type: 'string' },
    hasDecisionRecords: { type: 'boolean' },
    hasGlossary: { type: 'boolean' },
    backlogPath: { type: 'string' },
    files: { type: 'array', items: { type: 'string' } },
    skillPath: { type: 'string', description: 'absolute path to roles/consistency-check.md, resolved on disk' },
  },
}

const FINDINGS = {
  type: 'object',
  required: ['findings'],
  properties: {
    findings: {
      type: 'array',
      items: {
        type: 'object',
        required: ['claim', 'evidence', 'canonical', 'severity'],
        properties: {
          claim: { type: 'string', description: 'the defect in one sentence' },
          evidence: { type: 'string', description: 'file:line for every side, quoted' },
          canonical: { type: 'string', description: 'which side is right and why' },
          severity: { type: 'string', enum: ['correctness', 'impact', 'rot'] },
          mechanical: { type: 'boolean', description: 'true for dead links, drifted terms, typos' },
        },
      },
    },
  },
}

const VERDICT = {
  type: 'object',
  required: ['refuted', 'why'],
  properties: {
    refuted: { type: 'boolean' },
    why: { type: 'string' },
    correction: { type: 'string', description: 'if the finding is real but its evidence or canonical side is wrong' },
  },
}

const FILED = {
  type: 'object',
  required: ['items', 'commit'],
  properties: {
    items: { type: 'array', items: { type: 'string' } },
    commit: { type: 'string' },
    notes: { type: 'string' },
  },
}

// One agent per finding class so the classes run concurrently. The classes are
// named here; the role defines each one, and phase 2 is gated on docsAreSpec.
const CLASSES = [
  { key: 'contradictions', title: 'Cross-document contradictions, and intra-document self-contradiction' },
  { key: 'references', title: 'Reference integrity' },
  { key: 'residue', title: 'Residue of earlier versions' },
  { key: 'terminology', title: 'Terminology drift' },
  { key: 'decisions', title: 'Decision-record coherence' },
]

phase('Map')
const map = await agent(
  `Locate the delivery-team plugin's consistency-check role on disk — its file is \`roles/consistency-check.md\` under the installed plugin root, which is typically under ~/.claude/plugins/. Return its absolute path as skillPath; if the repo you are in IS the plugin, use its own copy. Read it, and read <repo>/.delivery-team/profile.md, then apply that role's "Before anything: applicability gate" exactly.

Return: whether the role applies at all and why; whether docs are spec; the docs root; whether the project declares decision records and a glossary; the backlog path; and the full list of files that make up the specification and the definitions it governs (the docs root, plus agent and skill definitions, manifests and the profile template if the project ships them).

Do not audit anything. This is inventory only.`,
  { schema: MAP, phase: 'Map' },
)

if (!map || !map.applicable) {
  log(`consistency-sweep does not apply here: ${map ? map.reason : 'inventory failed'}`)
  return { applicable: false, reason: map ? map.reason : 'inventory failed', filed: [] }
}

log(`${map.files.length} files in scope; docs are spec: ${map.docsAreSpec}`)

const classes = CLASSES.concat(
  map.docsAreSpec ? [{ key: 'spec-vs-code', title: 'Phase 2 — spec vs code (the whole section)' }] : [],
)

phase('Audit')
const verified = await pipeline(
  classes,
  cls =>
    agent(
      `You are auditing one class of defect across a specification. **Read ${map.skillPath} first — it defines the method, every finding class, and how to pick the canonical side — and follow it.** This prompt names your class and your scope; the role file says what the class means and how to judge it.

Your class, and only this class: **${cls.title}**, as that role defines it. Audit nothing outside it.

Files in scope:
${map.files.join('\n')}

Return each finding as: the claim in one sentence, quoted file:line evidence for every side, which side is canonical and why (resolve that per the role's rule, do not invent your own), and whether it is mechanical rot. Report nothing you could not substantiate by reading the files themselves. An empty findings list is a good answer when the class is clean.`,
      { label: `audit:${cls.key}`, phase: 'Audit', schema: FINDINGS },
    ),
  (result, cls) =>
    parallel(
      (result ? result.findings : []).map(f => () =>
        agent(
          `Try to REFUTE this claimed specification defect. You are not its author and you gain nothing by agreeing.

Claim: ${f.claim}
Evidence offered: ${f.evidence}
Canonical side offered: ${f.canonical}

Open the cited files and read them. Refute it if: the evidence does not say what is claimed; the two sides do not actually conflict when read in context; the pattern is the project's deliberate convention rather than a defect; the "canonical" side is the wrong one; or the finding restates a rule the spec deliberately states in two places with one owning and one pointing.

Default to refuted when you cannot substantiate the finding yourself. If the defect is real but the evidence or the canonical side is wrong, say so in the correction field rather than refuting it.`,
          { label: `verify:${cls.key}`, phase: 'Verify', schema: VERDICT },
        ).then(v => (v && !v.refuted ? { ...f, verifiedBy: cls.key, correction: v.correction } : null)),
      ),
    ),
)

const survivors = verified.flat().filter(Boolean)
const dropped = verified.flat().length - survivors.length
log(`${survivors.length} findings survived adversarial verification (${dropped} refuted)`)

if (survivors.length === 0) {
  return { applicable: true, filed: [], findings: 0, note: 'spec is self-consistent and matches its definitions; nothing filed' }
}

phase('File')
const real = survivors.filter(f => !f.mechanical)
const rot = survivors.filter(f => f.mechanical)

const filed = await agent(
  `File these verified specification defects as backlog items, following the "What you return" section of ${map.skillPath} exactly: one item per real defect at the backlog location in \`config.toml\` \`[backlog] dir\`, priority encoded in the filename, frontmatter \`by: qa (consistency-sweep)\`, and a body giving the claim, both sides quoted, the canonical resolution, and what the fix must change. Batch ALL mechanical rot into ONE low-priority item listing every instance.

Every item must satisfy the charter's item-shape contract — a stranger must be able to action it cold. **File findings; fix nothing**, not even a broken link.

Real defects (${real.length}):
${JSON.stringify(real, null, 2)}

Mechanical rot (${rot.length}), all into one item:
${JSON.stringify(rot, null, 2)}

Commit explicit-path — \`git add <each item file>\`, never \`git add -A\` — with a docs(backlog) subject. Run a plain \`git commit\` and pass no flags of your own. Do not push. Return the item filenames and the commit SHA.`,
  { phase: 'File', schema: FILED },
)

return {
  applicable: true,
  audited: map.files.length,
  classes: classes.length,
  findings: { surviving: survivors.length, refuted: dropped },
  filed: filed ? filed.items : [],
  commit: filed ? filed.commit : null,
}
