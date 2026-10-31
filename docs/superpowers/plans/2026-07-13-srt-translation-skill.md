# SRT Translation Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or
> superpowers:executing-plans. Steps use checkbox syntax. This session executes inline
> (user: "don't stop until you're done").

**Goal:** Arabic lecture YT auto-captions → re-segmented, re-timed, glossary-consistent English
`.srt` + review report + bilingual file, with an auto-growing master glossary.

**Architecture:** Word timeline → pause-based proto-segments → ~3-min blocks → parallel Claude
translator subagents (sentences as proto-segment ranges, `|` break marks, scripture via copied
`retrieval/`) → deterministic Python retime/assemble/lint → reviser pass → glossary harvest
(auto-merge new, hold conflicts) → report. Spec:
`docs/superpowers/specs/2026-07-13-srt-translation-skill-design.md`.

**Tech Stack:** Python 3.9+ stdlib-only (pytest dev-only), `yt-dlp` (URL path), copied
`retrieval/` + pinned fawazahmed0 datasets, Claude Code subagents.

## Global Constraints

- Pipeline imports stdlib only; `python -m …` run from repo root.
- The model never reads or writes timestamps; all timing math in Python.
- Subtitle limits: ≤42 chars/line, ≤2 lines, ≤20 CPS, 0.8–7.0 s per cue.
- Subagents WRITE their output file before self-check; failure isolation per block.
- Glossary conflicts never auto-apply; master merges are git-committed per run.
- Commit after each green task; never `git push`.

## Data structures (canonical, JSON)

- Word `{"w": str, "t0": float, "t1": float}` — seconds.
- `work/timeline.json` `{"source", "kind": "srt|vtt|json3", "words": [Word]}`
- Proto-segment `{"i": int, "w0": int, "w1": int, "text": str, "t0": float, "t1": float}`
  (`w0..w1` exclusive-end into words).
- `work/blocks.json` `{"segments": [Seg], "blocks": [{"n": int, "s0": int, "s1": int,
  "context": str}]}` — `s0..s1` INCLUSIVE proto-segment range.
- `work/translated/block_NNN.json` (subagent):
  `{"block": int, "sentences": [{"segs": [a, b], "type": "prose|quran|hadith", "en": str,
  "ref": str|null, "src": "dataset|fallback"|null, "flags": [str]}],
  "new_terms": [{"ar", "translit", "english", "kind": "term|name"}], "flags": [str]}`
  — `segs` inclusive; `en` carries `|` break marks.
- Cue `{"start": float, "end": float, "lines": [str]}`.

## Module interfaces

- `subs/srt_io.py`: `parse_ts(s)->float`, `fmt_ts(sec)->"HH:MM:SS,mmm"`,
  `parse_srt(text)->[{"index","start","end","text"}]` (tolerant: BOM/CRLF/`.`-millis/missing
  index; bad cue → skipped, collected in `parse_srt.errors`-style return tuple
  `(cues, warnings)`), `parse_vtt(text)->(cues, warnings)`, `compose_srt(cues)->str`.
- `subs/timeline.py`: `words_from_cues(cues)->[Word]` (overlap flatten: `eff_end_i =
  start_{i+1} if start_i < start_{i+1} < end_i else end_i`; char-proportional word spans;
  drops `[...]`-bracket noise tags), `words_from_json3(obj)->[Word]`.
- `subs/segment.py`: `proto_segments(words, pause=0.6, max_words=14)->[Seg]`,
  `make_blocks(segs, target_sec=180.0, context_sec=15.0)->[Block]`.
- `subs/retime.py`: `sentence_cues(en_marked, t0, t1)->(cues, warnings)` — the split/allocate/
  clamp/wrap algorithm (below); `wrap_lines(text, width=42)->[str]` (≤2 balanced lines);
  `cps(text, dur)->float`.
- `subs/assemble.py`: `load_translated(work)->[sentence dicts + block refs]`,
  `validate_tiling(block, sentences)->[str problems]`, `assemble(run_dir)->stats` writes
  `output/<slug>.en.srt`.
- `subs/lint.py`: `lint_run(run_dir, master)->{"problems": [...], "warnings": [...]}` — order/
  overlap/CPL/lines/CPS/duration/leftover-Arabic-chars/tiling-coverage/glossary-drift.
- `subs/glossary.py`: `fold(s)->str` (reuse `retrieval.normalize.normalize_arabic` + strip
  `ال/وال/فال/بال/كال/لل` prefix), `subset_for(text, master)->dict`,
  `harvest(run_dir, master_path)->{"added", "conflicts"}` (+ changelog append),
  `resolve(run_dir, master_path, accept:set)`.
- `subs/report.py`: `write_review(run_dir, harvest_result, lint_result)`,
  `write_bilingual(run_dir)`.
- `scripts/ingest_video.py`: `python -m scripts.ingest_video <url|file> --run runs/<slug>`
  → timeline.json + blocks.json + printed stats (words/segments/blocks/duration).
- `scripts/glossary.py`: `harvest|resolve|diff` CLI over `subs.glossary`.

## Retime algorithm (Task 5, the subtle one)

1. Pieces = `en_marked.split("|")`, trimmed; `text` = pieces joined with a space.
2. Fits one cue (`len(text) ≤ 84` and `dur ≤ 7.0` and `cps(text, dur) ≤ 20`) → one cue.
3. Else `k = max(ceil(chars/84), ceil(dur/7.0))` cues; pick `k-1` split points among piece
   boundaries greedily nearest ideal positions `i*chars/k` (monotonic); too few boundaries →
   split at the space nearest each remaining ideal position.
4. Durations ∝ chunk chars over `[t0, t1]`, butt-joined; a min-duration pass borrows time from
   the larger neighbor; clamp keeps monotonicity.
5. Overall `cps(text, t1-t0) > 20` cannot be fixed by splitting → emit anyway + warning
   (surfaces in lint/review; translator was instructed to condense).
6. `wrap_lines`: ≤42 → one line; else break at the space nearest the middle where both halves
   ≤ 42; no such space → hard warning, single overlong line kept.

## Tasks

### Task 1: Vendor retrieval + data tooling from the book repo
Copy `retrieval/`, `scripts/setup_data.py`, `scripts/run_status.py`, `data/MANIFEST.json`,
`data/surah_names.json`, `pytest.ini`, `requirements-dev.txt` from
`~/Documents/Translations/translate-islamic-book`; adapt paths if any are repo-specific;
`.venv` + pytest green on the copied retrieval tests (copy those too); run `setup_data.py`;
smoke `python -m retrieval.quran_lookup --match` on a verse from the sample. Commit.

### Task 2: `subs/srt_io.py` (TDD)
Tests: parse_ts variants (comma/dot millis), fmt_ts round-trip, parse the real sample head
(BOM absent, overlaps preserved raw), skip-malformed-cue warning, compose_srt formatting +
re-index, VTT header/`.`-millis. Commit.

### Task 3: `subs/timeline.py` (TDD)
Tests: overlap flatten rule (cue ends clamp to next start; normal SRTs untouched; degenerate
next-start ≤ start keeps own end), char-proportional word times sum to the span exactly (last
word ends at eff_end), bracket-tag drop, json3 fixture (`events[].segs[].utf8/tOffsetMs` +
`tStartMs/dDurationMs`). Commit.

### Task 4: `subs/segment.py` (TDD)
Tests: pause cut at gap ≥ 0.6 s, max_words hard cap, segments cover all words in order,
block target-duration grouping, inclusive s0/s1, context = tail text of previous block
(~context_sec worth of words), first block empty context. Commit.

### Task 5: `subs/retime.py` (TDD)
Tests per algorithm above: single-cue fit; k from CPL; k from max_dur; greedy boundary choice;
no-boundary fallback to spaces; duration ∝ chars; min-dur borrowing; monotonic non-overlap
tiling `[t0,t1]`; overall-CPS warning; wrap_lines balanced/one-line/no-space-warning. Commit.

### Task 6: `subs/glossary.py` + seed master (TDD)
Tests: fold (diacritics/hamza/ة/ى/tatweel/article prefixes), subset_for matches folded
substrings + always includes names + style, harvest auto-merges brand-new keys + appends
changelog + returns conflicts without applying, resolve applies only named keys, master write
is sorted/ensure_ascii=False. Seed `data/glossary.json` from the book repo's master (terms +
names + works; drop structure; rewrite style line for subtitles), create empty
`data/glossary-changelog.md`. Commit.

### Task 7: `subs/assemble.py` + `subs/lint.py` (TDD)
Tests: tiling validation (gap/overlap/misorder detected), assemble merges blocks in order into
composed SRT via retime, stats counts; lint fires each rule on crafted bad cues and passes the
assembled good output; leftover-Arabic detection; glossary-drift check (English rendering of a
folded-matched term differs from master). Commit.

### Task 8: `subs/report.py` + `scripts/ingest_video.py` + `scripts/glossary.py` (TDD-light)
Tests: review.md contains stats/flag/scripture/glossary sections from canned inputs;
bilingual.md stacks `[mm:ss]` + Arabic (from segs) + English; ingest CLI on the real sample
writes timeline+blocks with plausible stats (assert counts > 0 and durations monotonic);
yt-dlp path shells out only when input matches a URL (subprocess mocked in test). Commit.

### Task 9: Templates + SKILL.md
`templates/translator-subagent.md` + `templates/reviser-subagent.md` per spec Section 3 (three
lanes adapted to speech: prose/quran/hadith; segs-tiling contract; `|` marks; condense rule;
new_terms; WRITE-before-self-check; short status). `SKILL.md`: numbered pipeline (ingest →
prime glossary subset → pilot block → parallel waves gated by `run_status --gate` → validate →
revise → assemble → lint → harvest+commit → report), RESUME procedure, run layout. Commit.

### Task 10: End-to-end verification on the real sample
`ingest_video` on the Sirah 01 SRT → dispatch ONE real translator subagent on block 1 (pilot) →
validate tiling → retime+assemble that block → lint → eyeball the English cues vs the Arabic.
Fix what reality breaks. Commit. (Full-lecture run = separate user-triggered event, costed.)

## Out of plan

Editor web app (own spec, built after this ships). Whisper. Firestore.
