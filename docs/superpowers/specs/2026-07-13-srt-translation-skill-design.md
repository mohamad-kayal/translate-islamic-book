# SRT Translation Skill — Design

**Date:** 2026-07-13 · **Status:** approved through Section 1 in conversation; remainder per
"go for it, don't stop until you're done".

## Goal

A Claude Code skill that translates Arabic Islamic-lecture YouTube auto-captions into
publication-quality English subtitles, with a **live glossary** that grows on every run, plus a
review report and a bilingual review file. Separate project from `translate-islamic-book`
(functionality copied where useful — no shared files); its own master glossary.

## Requirements (from brainstorm)

- **Input:** YouTube auto-captions. Two paths: (a) a YouTube URL — skill fetches json3 captions
  via `yt-dlp` (word-level timings); (b) a user-supplied `.srt`/`.vtt` export (cue-level timing
  only, often with *overlapping* rolling-caption timestamps — confirmed in the real sample).
- **Content:** Islamic lectures/lessons (MSA + dialect, unpunctuated ASR text, ta-marbuta/hamza
  ASR mangling, quoted Qur'an/hadith throughout). Primary corpus: Ahmad al-Sayyid lecture series.
- **Scripture:** established translations — quoted Qur'an/hadith retrieved via the book repo's
  `retrieval/` machinery (copied here) and datasets; spoken quotes are often partial/garbled, so
  unmatched quotes fall back to model translation + a review flag. Qur'an English is
  mechanically verified as a substring of the dataset rendering.
- **Glossary:** auto-grow. New terms merge into the master automatically at end of run with a
  per-run changelog entry; **conflicts** (existing Arabic key, different rendering) never
  auto-apply — they go to `review.md` + a proposals file and are applied via an explicit resolve
  command. Master is git-tracked so growth is inspectable/revertible.
- **Deliverables per run:** `output/<slug>.en.srt` (re-segmented, re-timed, reading-speed
  compliant), `output/review.md`, `output/bilingual.md`.
- **Style:** faithful by default; **condense when over reading-speed limits** (trim repetitions,
  يعني-padding). Limits: ≤42 chars/line, ≤2 lines, ≤20 CPS, 0.8–7.0 s per cue.
- **Architecture:** skill + Claude subagents (Approach A). The model does linguistics only;
  Python does all timestamp math. The model never reads or writes a timestamp.

## Pipeline (approved Section 1)

One run = one video, in `runs/<slug>/` (`work/` intermediates, `output/` deliverables), resumable
at every stage. Stages:

1. **Fetch/ingest** (`scripts/ingest_video.py`, package `subs/`): URL → `yt-dlp` json3, or file →
   tolerant SRT/VTT parser. Both normalize to the core data structure, the **word timeline**
   `[{w, t0, t1}, …]` → `work/timeline.json`. json3 gives exact word times; overlap-style SRT
   assigns cue N the effective span `[start_N, start_{N+1})` (last cue keeps its own end) and
   distributes words proportionally by character length. `[موسيقى]`/`[تصفيق]` bracket tags are
   dropped (their spans become silence).
2. **Proto-segmentation** (`subs/segment.py`): cut the timeline at speech pauses (gap ≥ the
   adaptive pause threshold; hard cap so no proto-segment exceeds ~14 words) into small numbered
   proto-segments — mechanical anchor units, no linguistic claims. Group into **blocks** of
   ~3 min of speech, each carrying the previous block's tail (~15 s of text) as
   context-not-to-translate → `work/blocks.json`.
3. **Translate** (parallel Claude subagents, pilot-gated, usage-gated): one subagent per block
   gets the numbered proto-segments (with per-segment duration hints, e.g. `[17|2.3s] …`), the
   glossary subset lexically matched to its text (+ all names + conventions), the brief
   (`templates/translator-subagent.md`), and retrieval instructions. It writes
   `work/translated/block_NNN.json` BEFORE its final self-check (cutoff-safe, book-repo
   discipline) and returns a short status. Output schema per sentence:
   `{"segs": [a, b], "type": "prose|quran|hadith", "en": "English | with breaks", "ref": null or
   "3:164" / "bukhari 1", "src": "dataset|fallback" (scripture only), "flags": […]}` plus
   block-level `"new_terms": [{"ar", "translit", "english", "kind": "term|name"}]`.
   Python validates each block's sentence ranges **tile the block exactly** (no gap, no overlap,
   in order); a violation gets one re-dispatch, then hard-fails the block (others unaffected).
4. **Retime & emit** (`subs/retime.py` + `subs/assemble.py`): a sentence's span = its
   proto-segments' word times. If its English fits one cue → one cue; else split at the model's
   `|` marks choosing the split set nearest ideal proportional positions; allocate sub-spans by
   character count; clamp to duration bounds; keep cues monotonic and non-overlapping; wrap each
   cue into ≤2 balanced lines at spaces. Emit `output/<slug>.en.srt` (UTF-8, re-indexed).
5. **Revise → lint → harvest → report**: reviser subagents (cheaper model) re-check each block
   sentence-by-sentence against the Arabic, applying minor fixes to `work/translated/*.json`;
   majors → one re-translate round. `subs/lint.py` checks order/overlap/CPL/lines/CPS/duration/
   leftover-Arabic/coverage/glossary drift. Glossary harvest (below). `subs/report.py` writes
   `review.md` (stats, scripture list + verify status, fallbacks, flags, CPS residuals, glossary
   changes) and `bilingual.md` (per sentence: `[mm:ss]`, Arabic, English — stacked).

`work/translated/block_NNN.json` files are the checkpoint unit: a resumed run dispatches only
missing blocks; at scale the revise pass runs as a resumable Workflow
(`pipeline(blocks, revise, fixMajors)`), as proven in the book repo.

## Section 2 — Live glossary

**Master:** `data/glossary.json`, git-tracked, same shape family as the book repo for future
editor compatibility, minus `structure` (no headings in subtitles):

```json
{
  "style": "al- (no sun-letter assimilation); ' for ayn/hamza; no macrons; keep ﷺ as ﷺ in subtitles; term first use: english (translit), translit alone after",
  "terms": { "التوحيد": {"translit": "tawhid", "english": "the Oneness of Allah"} },
  "names": { "ابن تيمية": "Ibn Taymiyyah" },
  "works": { "حجية السنة": "Hujjiyyat al-Sunnah" }
}
```

Seeded from the book repo's master (terms + names carry over; they're the same author's
vocabulary). Subtitle gloss style differs from the book's pandoc form: on a term's first
appearance in a video, `english (translit)`; afterwards the short form — no `{lang=ar}` spans,
no Arabic inline (screen space).

**Matching key:** orthography-folded (diacritics stripped, alef/hamza unified, ة/ه folded,
definite article stripped) via functions copied from `retrieval/normalize.py`. Stored keys keep
their written form; matching and dedup use the folded key.

**Injection (per block):** lexical match of folded glossary keys against the block's folded text;
matched `terms`/`works` + ALL `names` + the `style` line go into the subagent brief. Keeps
prompts small and cacheable.

**Harvest (end of run, `scripts/glossary.py`):**
- `harvest <run-dir>`: collect `new_terms` from all block files, dedup by folded key, then:
  - brand-new keys → **auto-merged** into `data/glossary.json`, and an entry appended to
    `data/glossary-changelog.md` (`## 2026-07-13 — <slug>` + one line per added term);
  - keys that exist with a different rendering → **never auto-applied**; written to
    `runs/<slug>/work/glossary-proposals.json` and listed in `review.md`.
- `resolve <run-dir> --accept <ar1,ar2>`: apply named conflict proposals to the master (the
  explicit-accept semantics of the book repo's `merge --only`).
- Master merge is one git commit per run → the "live document" has a visible, revertible history.

## Section 3 — Subagent contracts

**Translator** (`templates/translator-subagent.md`), one block per agent:
- Inputs (in the dispatch prompt): block file path, previous-tail context, glossary-subset text,
  output path, run conventions (series name, speaker).
- Duties: group proto-segments into sentences (a sentence = contiguous proto-segment range);
  translate faithfully; condense when the time budget is tight (segment duration hints);
  mark clause-boundary break points with `|` roughly every ≤40 chars; detect quoted Qur'an/hadith
  and retrieve (`python -m retrieval.quran_lookup --match …` / `hadith_lookup --match … --prefer
  <coll>`), pasting the established English trimmed to the spoken portion, `src=dataset` + `ref`;
  unmatched → translate naturally, `src=fallback`, flag; report `new_terms` (recurring Islamic
  terms/proper nouns it rendered that aren't in its glossary subset).
- Output: WRITE the block JSON before self-check; return short status (sentence count, scripture
  count, flags).
- Conventions: ﷺ kept as ﷺ; other honorifics abbreviated ("(AS)", "(RA)") to save screen space;
  numbers as digits; no ending punctuation dropped (English gets normal punctuation — the
  translation adds it since ASR has none).

**Reviser** (`templates/reviser-subagent.md`), one block per agent, cheaper model: re-read the
Arabic proto-segments vs the English sentences; fix minors in place (mishearing-level errors,
dropped clauses, glossary drift, missing condensation); report majors (wrong sentence grouping,
missed scripture) for a re-translate round; never touch `segs` ranges without flagging.

## Section 4 — Repo layout

```
SRT-translator/
├─ SKILL.md                  # the pipeline the orchestrating agent runs
├─ subs/                     # stdlib-only Python package
│  ├─ srt_io.py              # tolerant SRT/VTT parse + SRT compose
│  ├─ timeline.py            # json3/SRT → word timeline (overlap flattening here)
│  ├─ segment.py             # pauses → proto-segments → blocks
│  ├─ retime.py              # sentence spans → cue splits + timestamps (pure math)
│  ├─ assemble.py            # translated block JSONs → .en.srt
│  ├─ lint.py                # CPS/CPL/overlap/coverage/drift checks
│  ├─ report.py              # review.md + bilingual.md
│  └─ glossary.py            # folded matching, inject subset, harvest/merge/changelog
├─ scripts/
│  ├─ ingest_video.py        # URL-or-file → timeline.json + blocks.json (CLI)
│  ├─ glossary.py            # harvest/resolve/diff CLI (wraps subs.glossary)
│  ├─ run_status.py          # copied from book repo (usage gate)
│  └─ setup_data.py          # copied/adapted: pinned quran+hadith datasets + MANIFEST
├─ retrieval/                # copied verbatim from book repo (+ its cache)
├─ data/                     # glossary.json (master, tracked), glossary-changelog.md,
│                            # MANIFEST.json; quran/ + hadith/ downloaded (gitignored)
├─ templates/                # translator-subagent.md, reviser-subagent.md
├─ tests/                    # pytest
├─ runs/                     # per-video workdirs (gitignored)
└─ editor/                   # sub-project 2 (own spec)
```

Python 3.9+, stdlib-only pipeline (book-repo convention). External: `yt-dlp` (URL path only),
system `curl` for dataset download. Commits local only; push is user-opt-in.

## Section 5 — Error handling

- Tolerant SRT parse (BOM, CRLF, missing indices, `HH:MM:SS.mmm` variants); malformed cue →
  skip + warn, never crash.
- Overlapping rolling captions: flatten rule in timeline (documented above), verified against the
  real sample (1,516 cues).
- Subagent death / garbage output: JSON schema + tiling validation; one re-dispatch; then the
  block hard-fails alone (book-repo failure isolation), run reports it.
- Usage gate before every wave (`run_status --gate`, fail-open PROCEED-degraded); on PAUSE write
  `RESUME.md`; resume dispatches only missing blocks.
- Content-filter 400s on sensitive passages: re-dispatch with the academic-translator framing
  (book-repo remedy).
- Timing invariants asserted at assemble: monotonic, non-overlapping, within video duration.

## Section 6 — Testing

TDD for the real logic; golden data from the actual sample file (first cues of Sirah 01):
- `srt_io`: parse the sample head (overlaps, Arabic, BOM), compose round-trip.
- `timeline`: overlap flattening (cue N ends at start of N+1), proportional word times sum
  exactly to span; json3 path with a small fixture.
- `segment`: pause-threshold cuts, max-words cap, block grouping determinism, context tails.
- `retime`: split choice at `|` marks, char-proportional allocation, min/max duration clamps,
  CPS computation, two-line balanced wrap; property: output cues tile the sentence span in order.
- `glossary`: folded matching (ال/ة/hamza cases), inject subset selection, harvest auto-merge vs
  conflict hold, changelog append, resolve --accept.
- `lint`: each rule fires on a crafted bad input and stays quiet on good.
- Integration: sample SRT → timeline → blocks → (canned block JSON) → retime → assemble →
  lint-clean output.

Subagent behavior is verified by a pilot block on the real sample (not unit-testable).

## Out of scope (this spec)

The mobile editor web app — sub-project 2, spec'd separately
(`2026-07-13-srt-editor-webapp-design.md`). Whisper transcription, bilingual .ass output,
cleaned-Arabic SRT: not now (YAGNI).
