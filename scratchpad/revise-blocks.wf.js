export const meta = {
  name: 'revise-blocks',
  description: 'Revise a specified list of already-translated blocks (recover quota-interrupted revise passes)',
  phases: [{ title: 'Revise', detail: 'one reviser per listed block; a MAJOR triggers one re-translate + re-revise' }],
}

const A = typeof args === 'string' ? JSON.parse(args) : args
const RUN = A.run                    // e.g. 'runs/riyad-11'
const BLOCKS = A.blocks              // list of block numbers needing a (re)revise
const ROOT = '/Users/employee/Documents/SRT-translator'

const CHECK_SCHEMA = {
  type: 'object', additionalProperties: false,
  properties: { ok: { type: 'boolean' }, problems: { type: 'array', items: { type: 'string' } } },
  required: ['ok', 'problems'],
}
const REVISE_SCHEMA = {
  type: 'object', additionalProperties: false,
  properties: {
    block: { type: 'integer' }, minor_fixes: { type: 'integer' },
    majors: { type: 'array', items: { type: 'string' } },
    flags: { type: 'array', items: { type: 'string' } },
  },
  required: ['block', 'minor_fixes', 'majors', 'flags'],
}

const trPrompt = (b, extra) =>
  `You are translating block ${b} of ${RUN}. Read templates/translator-subagent.md and ${RUN}/work/DISPATCH.md and follow them exactly. Work from the repo root (${ROOT}) with .venv/bin/python for every command. Start with \`.venv/bin/python -m scripts.block_brief show ${RUN} --block ${b}\`, retrieve any quoted Qur'an/hadith, WRITE the output file, then self-check with \`.venv/bin/python -m scripts.block_brief check ${RUN} --block ${b}\` until it prints OK. Return only the short status.${extra || ''}`
const chkPrompt = (b) =>
  `Run exactly this command from ${ROOT} and report its result: \`.venv/bin/python -m scripts.block_brief check ${RUN} --block ${b}\`. If the output begins with "OK:" set ok=true and problems=[]. Otherwise ok=false with each problem line in problems[]. Edit nothing.`
const rvPrompt = (b) =>
  `You are revising block ${b} of ${RUN}. Read templates/reviser-subagent.md and follow it exactly. Work from the repo root (${ROOT}) with .venv/bin/python. Fix minors in place; report majors. Return the short status: block, minor_fixes (count), majors[], flags[].`

async function reviseBlock(b) {
  let rev = await agent(rvPrompt(b), { model: 'sonnet', agentType: 'general-purpose', phase: 'Revise', label: `rv:${b}`, schema: REVISE_SCHEMA })
  if (!rev) rev = await agent(rvPrompt(b), { model: 'sonnet', agentType: 'general-purpose', phase: 'Revise', label: `rv:${b}(retry)`, schema: REVISE_SCHEMA })
  rev = rev || { block: b, minor_fixes: 0, majors: [], flags: [] }
  if (rev.majors && rev.majors.length) {
    await agent(trPrompt(b, ` A reviser flagged MAJOR issues to fix: ${rev.majors.join(' | ')}. Re-translate the block addressing them (you may re-tile segs if a quote needs its own sentence).`),
      { model: 'sonnet', agentType: 'general-purpose', phase: 'Revise', label: `fix:${b}` })
    await agent(chkPrompt(b), { model: 'haiku', agentType: 'general-purpose', phase: 'Revise', label: `chk:${b}(fix)`, schema: CHECK_SCHEMA })
    const rev2 = await agent(rvPrompt(b), { model: 'sonnet', agentType: 'general-purpose', phase: 'Revise', label: `rv:${b}(2)`, schema: REVISE_SCHEMA })
    if (rev2) { rev2.majors = rev2.majors || []; return rev2 }
  }
  return rev
}

phase('Revise')
const rv = await parallel(BLOCKS.map(b => () => reviseBlock(b)))
const withMajors = rv.filter(r => r && r.majors && r.majors.length).map(r => ({ block: r.block, majors: r.majors }))
const totalMinors = rv.reduce((s, r) => s + ((r && r.minor_fixes) || 0), 0)
log(`revise: ${BLOCKS.length} blocks; ${totalMinors} minor fixes; ${withMajors.length} still with majors`)
return { run: RUN, revised: BLOCKS, revise_majors: withMajors, minor_fixes: totalMinors }
