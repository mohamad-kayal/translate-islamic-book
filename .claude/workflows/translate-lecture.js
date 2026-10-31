export const meta = {
  name: 'translate-lecture',
  description: 'Translate + revise all blocks of an ingested lecture run (Sonnet subagents, Haiku checks)',
  phases: [
    { title: 'Translate', detail: 'one translator subagent per missing block, then a structural check; one retry on failure' },
    { title: 'Revise', detail: 'one reviser subagent per block; a MAJOR triggers one re-translate + re-revise' },
  ],
}

const A = typeof args === 'string' ? JSON.parse(args) : args
const RUN = A.run                              // e.g. 'runs/riyad-01'
const ROOT = A.root                            // the repo root, e.g. '/Users/me/translate-islamic-book'
const ALL = Array.from({ length: A.total }, (_, i) => i)
const DONE = new Set(A.done || [])
const MISSING = ALL.filter(b => !DONE.has(b))

const CHECK_SCHEMA = {
  type: 'object', additionalProperties: false,
  properties: { ok: { type: 'boolean' }, problems: { type: 'array', items: { type: 'string' } } },
  required: ['ok', 'problems'],
}
const REVISE_SCHEMA = {
  type: 'object', additionalProperties: false,
  properties: {
    block: { type: 'integer' },
    minor_fixes: { type: 'integer' },
    majors: { type: 'array', items: { type: 'string' } },
    flags: { type: 'array', items: { type: 'string' } },
  },
  required: ['block', 'minor_fixes', 'majors', 'flags'],
}

const trPrompt = (b, extra = '') =>
  `You are translating block ${b} of ${RUN}. Read templates/lecture-translator.md and ${RUN}/work/DISPATCH.md and follow them exactly. Work from the repo root (${ROOT}) with .venv/bin/python for every command. Start with \`.venv/bin/python -m scripts.block_brief show ${RUN} --block ${b}\`, retrieve any quoted Qur'an/hadith with the retrieval CLIs, WRITE the output file, then self-check with \`.venv/bin/python -m scripts.block_brief check ${RUN} --block ${b}\` until it prints OK. Return only the short status the template asks for.${extra}`

const chkPrompt = (b) =>
  `Run exactly this command from ${ROOT} and report its result: \`.venv/bin/python -m scripts.block_brief check ${RUN} --block ${b}\`. If the output begins with "OK:" set ok=true and problems=[]. Otherwise set ok=false and put each problem line into problems[]. Do nothing else — do not edit any file.`

const rvPrompt = (b) =>
  `You are revising block ${b} of ${RUN}. Read templates/lecture-reviser.md and follow it exactly. Work from the repo root (${ROOT}) with .venv/bin/python. Fix minors in place; report majors. Return the short status the template asks for, as: block, minor_fixes (count), majors[], flags[].`

async function checkBlock(b, tag) {
  const c = await agent(chkPrompt(b), { model: 'haiku', agentType: 'general-purpose', phase: 'Translate', label: `chk:${b}${tag || ''}`, schema: CHECK_SCHEMA })
  return c || { ok: false, problems: ['check agent returned null'] }
}

async function translateBlock(b) {
  await agent(trPrompt(b), { model: 'sonnet', agentType: 'general-purpose', phase: 'Translate', label: `tr:${b}` })
  let chk = await checkBlock(b)
  if (!chk.ok) {
    await agent(trPrompt(b, ' The previous attempt FAILED its structural check — redo it carefully so the sentences tile the whole block.'),
      { model: 'sonnet', agentType: 'general-purpose', phase: 'Translate', label: `tr:${b}(retry)` })
    chk = await checkBlock(b, '(retry)')
  }
  return { block: b, ok: chk.ok, problems: chk.problems }
}

async function reviseBlock(b) {
  let rev = await agent(rvPrompt(b), { model: 'sonnet', agentType: 'general-purpose', phase: 'Revise', label: `rv:${b}`, schema: REVISE_SCHEMA })
  if (!rev) {
    // reviser died (e.g. API error mid-response) — retry once so the block still gets a QA
    // pass rather than silently defaulting to "no majors" and shipping unrevised.
    rev = await agent(rvPrompt(b), { model: 'sonnet', agentType: 'general-purpose', phase: 'Revise', label: `rv:${b}(retry)`, schema: REVISE_SCHEMA })
  }
  rev = rev || { block: b, minor_fixes: 0, majors: [], flags: [] }
  if (rev.majors && rev.majors.length) {
    await agent(trPrompt(b, ` A reviser flagged MAJOR issues to fix: ${rev.majors.join(' | ')}. Re-translate the block addressing them specifically.`),
      { model: 'sonnet', agentType: 'general-purpose', phase: 'Revise', label: `fix:${b}` })
    await checkBlock(b, '(fix)')
    const rev2 = await agent(rvPrompt(b), { model: 'sonnet', agentType: 'general-purpose', phase: 'Revise', label: `rv:${b}(2)`, schema: REVISE_SCHEMA })
    if (rev2) { rev2.majors = rev2.majors || []; return rev2 }
  }
  return rev
}

phase('Translate')
const tr = await parallel(MISSING.map(b => () => translateBlock(b)))
const failed = tr.filter(r => !r || !r.ok).map(r => r && r.block)
log(`translate: ${tr.filter(r => r && r.ok).length}/${MISSING.length} ok${failed.length ? `; STILL FAILING: ${failed.join(',')}` : ''}`)

phase('Revise')
const rv = await parallel(ALL.map(b => () => reviseBlock(b)))
const withMajors = rv.filter(r => r && r.majors && r.majors.length).map(r => ({ block: r.block, majors: r.majors }))
const totalMinors = rv.reduce((s, r) => s + ((r && r.minor_fixes) || 0), 0)
log(`revise: ${rv.length} blocks; ${totalMinors} minor fixes; ${withMajors.length} blocks had majors (re-translated)`)

return { run: RUN, translate_failed: failed, revise_majors: withMajors, minor_fixes: totalMinors }
