---
name: translate-srt
description: Translate Arabic Islamic-lecture YouTube auto-captions into publication-quality
  English subtitles — cues are re-segmented into sentences and re-timed by deterministic Python
  (the model never touches a timestamp); quoted Qur'an/hadith come verbatim from bundled
  datasets; a live master glossary grows on every run. Use when the user wants an Arabic .srt/
  .vtt or a YouTube video's Arabic captions translated to English subtitles.
---

# Translate Arabic lecture captions → English SRT

Run every command from the repo root (`cd "$(git -C "${CLAUDE_SKILL_DIR}" rev-parse --show-toplevel)"`;
other agents: resolve this file's real path, `<repo>/skills/<name>/SKILL.md`, and follow
`<repo>/AGENTS.md`), with `python` meaning `.venv/bin/python`. One video is
one run: `runs/<slug>/`. First time here: `./install.sh`.

## Non-negotiables

- Scripture is retrieved, never model-written: quoted Qur'an/hadith English comes verbatim
  (possibly trimmed) from the datasets, and `block_brief check` compares it word by word; failures
  become flagged fallbacks in `review.md`.
- The model never reads or writes timestamps — all timing math is Python (`subs/retime.py`).
- Glossary conflicts never auto-apply. New terms auto-merge (that's the live glossary); a
  changed rendering of an existing term waits for the user in `review.md`. Do not submit fixed or
  author-profile-only terms for Sheikh Ahmad Al-Sayyid as new master-glossary entries.
- Subagents WRITE their block file before their final self-check.
- Never `git push`. The end-of-run glossary commit is local.

## Pipeline

1. **Ingest** — `python -m scripts.ingest_video <url-or-file> --run runs/<slug>`
   (URL → yt-dlp json3 word timings; .srt/.vtt → tolerant parse + rolling-overlap flattening).
   Prints `words/segments/blocks/duration`. Sanity-check: duration ≈ video length; skim the
   first segments of `runs/<slug>/work/blocks.json` for garbage.
2. **Prime** — read `data/glossary.json`; then check `data/series/` for this series' notes
   file (e.g. `data/series/sirah.md` for `sirah-NN` runs) and fold it into
   `runs/<slug>/work/DISPATCH.md`. New series → start a notes file (speaker, series title,
   format, coined renderings). The glossary subset is injected automatically per block;
   series notes carry what the glossary can't. For Sheikh Ahmad bin Yusuf Al-Sayyid (أحمد السيد),
   also read `docs/translation-manuals/sheikh-ahmad-al-sayyid.md`; its fixed terms and style
   override conflicting series notes or shared-glossary values for this run. Record those choices
   in DISPATCH.md, not the shared glossary. If authorship is uncertain, ask or flag it.
3. **Pilot** — dispatch ONE translator subagent (Agent tool, `run_in_background: false`) for
   block 0 with a prompt of this shape (adding DISPATCH.md to the reading list when it exists):

   > You are translating block 0 of runs/<slug>. Read templates/lecture-translator.md and
   > follow it exactly. Work from the repo root with .venv/bin/python.

   Then `python -m scripts.block_brief check runs/<slug> --block 0` and READ the block file —
   judge sentence grouping, fidelity, condensation, scripture handling. Fix the dispatch
   prompt/DISPATCH.md if the pilot shows drift; re-run the pilot if it was wrong.
4. **Gate + waves** — before each wave:
   `python -m scripts.run_status runs/<slug>/work --gate` (missing blocks + PROCEED/PAUSE;
   fail-open). On PAUSE: write `runs/<slug>/RESUME.md` (state + next wave) and stop cleanly.
   Dispatch translator subagents for the missing blocks in parallel waves of ~8 (same one-line
   prompt, different block numbers). A dead/garbled agent costs only its block: `check` fails →
   re-dispatch that block once; if it fails again, hard-fail the block and report it.
   Past ~one wave (a whole lecture, dozens of blocks) run this fan-out as a Workflow instead —
   see **Scale** below (Claude Code only).
5. **Validate** — `run_status` shows 0 missing; `block_brief check` passes for every block.
6. **Revise** — one reviser subagent per block (cheaper model is fine) with:

   > You are revising block N of runs/<slug>. Read templates/lecture-reviser.md and follow it
   > exactly. Work from the repo root with .venv/bin/python.

   Minors are fixed in place by the reviser; each MAJOR gets one re-translate round (step 4
   for that block, then re-revise it). At whole-lecture scale run this as a Workflow too
   (see **Scale**).
7. **Finish** — `python -m scripts.finish_lecture runs/<slug>` (assemble → lint → harvest →
   review.md + bilingual.md; also copies `glossary.json`, this run's `bilingual.md` and
   `.en.srt` into `editor/` so the editor app auto-loads them when served). Add `--italics`
   if the user wants quran/hadith cues wrapped in `<i>` tags (standard subtitle convention;
   ask once per series and note the answer in the series file). Lint problems = fix and
   re-run (usually a subagent left Arabic in `en`, or tiling broke during revision). Then
   update `data/series/<series>.md` (new episode line + any renderings coined this run) and
   commit: `git add data/glossary.json data/glossary-changelog.md editor/glossary.json
   data/series/ && git commit -m "glossary: <slug>"`. `python -m scripts.gate runs/<slug>` must
   exit 0 before you call the lecture finished.
8. **Deliver + sign-off** — give the user `runs/<slug>/output/<slug>.en.srt`, walk them
   through `review.md` (scripture fallbacks, flags, CPS residuals — all timestamped,
   glossary conflicts). For proofing, offer the editor: `python3 -m http.server 8777` from
   `editor/` auto-loads the current glossary + this run's bilingual review. Conflicts they
   accept: `python -m scripts.glossary resolve runs/<slug> --accept <ar1,ar2>` (+ commit).

## Scale — big jobs run as a resumable Workflow (Claude Code)

Manual Agent waves (steps 4, 6) are right for a short clip — up to about one wave. For a whole
lecture (dozens of blocks, more than one wave) run the model-touched fan-out as a Workflow
instead: it survives interruptions, a dead agent costs only its block, and the
translate→check→re-dispatch loop is encoded once. Invoking this skill is itself the opt-in.
`.claude/workflows/translate-lecture.js` is the saved script, with
`args` = `{run, root, total, done}`; `revise-blocks.js` re-revises a list of blocks.

- **Translate** — `pipeline(blocks, translateStage, checkStage)`: `translateStage` dispatches one
  translator subagent per block (same one-line prompt as step 3, different block number);
  `checkStage`'s agent runs `block_brief check` and returns a `{block, ok, majors[], flags[]}`
  StructuredOutput. A failing block is re-dispatched once, then hard-failed and reported.
- **Revise** — `pipeline(blocks, reviseStage, fixMajorsStage)` with a
  `{block, fixes, majors[], flags[]}` schema; each MAJOR triggers one re-translate round.
- The orchestrator is plain JS — no bash, no timestamps — so the `run_status` gate is replaced by
  the pipeline's own per-block accounting, and every non-negotiable still holds because the agents
  read the same templates. If `args` arrives as a JSON string, `JSON.parse` it first.
- Only the model-touched steps fan out. `ingest_video` and `finish_lecture` stay one-time CLI
  calls, run once before and after the Workflow.

## Resume after interruption

`python -m scripts.run_status runs/<slug>/work --gate` — completed block files are never
discarded; dispatch only the missing blocks (step 4) and continue. If `RESUME.md` exists, it
says where the run stopped and why.
