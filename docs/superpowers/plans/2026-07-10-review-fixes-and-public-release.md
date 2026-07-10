# 2026-07-10 — Review-round fixes + public-release readiness

## Context

A full skill review (2026-07-10, after four shipped books) found: (a) the author's prose — most
of every book — has no independent QA (the translator subagent self-checks its own output);
(b) two confirmed retrieval holes — `identify_span` returns only the FIRST location of a repeated
Qur'anic phrase (verified live: `ولقد يسرنا القرآن للذكر` → 54:17 with no signal that 54:22/32/40
exist), and hadith ranking's recall tie-break favors short matn-only entries (verified live:
`إنما الأعمال بالنيات` → Abu Dawud 2201, not Bukhari 1) — both produce plausible-but-wrong
citations that `out.verify` cannot catch; (c) hadith lookup costs ~11 s per call because it
rebuilds its index every invocation; (d) the battle-tested orchestration conventions (write-your-
own-chunk-file, isnad→matn marker rule, per-book DISPATCH.md) live only in run artifacts — the
committed template still says "return the markdown", contradicting proven practice; (e) datasets
are pinned to a *floating* `@1` jsDelivr tag with no checksums; (f) recurring dataset-English
typos (the Thawban "last"→"cast") must be re-flagged manually in every book.

Goal, per the user: fix all of it, to a standard **good enough to publish the repo publicly**.
Publishing itself (remote, push) is a separate, explicitly-authorized step — this plan only makes
the repo ready.

## Non-negotiables (unchanged)

Sacred text is retrieved, never LLM-written; `out.verify` enforces it. Citations follow the
author; wording follows the dataset. English-fix and glossary changes require user sign-off.
Existing books' outputs are not modified (their content is sign-off-gated).

## Tasks

### T1 — Index cache (speed: 11 s → target < 2.5 s per hadith lookup)
New `retrieval/cache.py`: `load_cached(name, source_paths, build, schema)` — pickle payload at
`data/.cache/<name>.pkl` guarded by a fingerprint (per-source `(path, mtime_ns, size)` + integer
`SCHEMA` version). Any mismatch or exception → rebuild and rewrite (fail open). `RETRIEVAL_NO_CACHE=1`
disables. HadithIndex caches the parsed `entries` list (inverted index rebuilt at load — cheap);
QuranIndex caches the three parsed editions. `data/.cache/` is already ignored via `data/`.
english-fixes.json (T4) joins the hadith fingerprint sources.
**Tests:** hit, miss, source-change invalidation, corrupt pickle, env kill-switch, schema bump.

### T2 — Hadith ranking: author-aware + canonical
`HadithIndex.match(query, min_conf, prefer=None)`: shortlist = candidates within `EPS = 0.02`
containment of the best; winner = first by `(preferred, canonical rank, recall)` where
`CANONICAL` = bukhari, muslim, abudawud, tirmidhi, nasai, ibnmajah, malik, then nawawi/qudsi/
dehlawi (derivative collections last). Result gains `alternates` (≤ 3 other shortlist entries,
distinct collections: coll/num/confidence). Below `min_conf`, the CLI returns
`{"matched": false, "nearest": {...best candidate summary...}}` instead of a bare miss.
CLI: `--prefer <collection>`. Template (T7): pass the author's takhrij collection as `--prefer`.
**Tests:** same matn in two collections — canonical wins ties; `prefer` overrides canonical;
alternates listed; nearest on sub-threshold; invalid prefer rejected.

### T3 — Qur'an repeated phrases (mutashabihat) + nearest
`QuranIndex.identify_spans(query, cap=20)`: ALL occurrences (finditer within each surah corpus,
all surahs), mushaf order. `identify_span` keeps its behavior (first hit) for compatibility.
`lookup()` adds `n_locations` (true count), `locations` (capped, primary first, each with
`ref_en`), `locations_truncated`. Near-miss: word→ayah inverted index built at init; on no match
return `nearest`: top ≤ 3 ayat by query-token containment ≥ 0.5, each with surah/ayah/score/arabic.
Template rule (T7): `n_locations > 1` → the author's printed ref decides; author silent → choose
by context and flag in the status message.
**Tests:** phrase repeated across surahs and within one surah (fixture editions); cap +
truncated flag; nearest on a one-word-off query; unique phrase → `n_locations = 1`.

### T4 — Sign-off-gated English fixes + mojibake flagging
`data/english-fixes.json` (tracked; `.gitignore` gains `!data/english-fixes.json`):
`{"fixes": [{"collection", "number", "old", "new", "note", "approved": "YYYY-MM-DD"}]}` applied
as exact `old→new` replacements when HadithIndex loads records; a fix whose `old` no longer
occurs prints a stderr warning (dataset drift). Ships EMPTY — the two known candidates (Thawban
Abu Dawud 4297 "last"→"cast" and its stray "Messenger of Allah (ﷺ):") go to the user as
proposals, entering the file only after sign-off. SKILL harvest step (T7) adds "English-fix
proposals" to review.md. `out.verify` flags U+FFFD in any quran/hadith block body;
`hadith_lookup` returns `english_warning` when the retrieved English contains U+FFFD.
**Tests:** fix applied at load; absent file OK; stale `old` warns; verify flags U+FFFD;
warning field present.

### T5 — Deterministic lint (`out/lint.py`)
CLI: `python -m out.lint <work_dir> [--glossary PATH]` — reads `translated/*.md`, plus `book.md`,
`chunks.json`, `manifest.json` when present; prints verify-style JSON `{"problems", "warnings"}`.
**problems** (would corrupt output): per-chunk marker imbalance (reuse verify's checker),
malformed marker openers (`<!-- quran`, missing attrs), leftover `[[H]]`/`[[HA]]` in book.md,
unclosed `^[` footnote. **warnings** (review): duplicate heading at chunk seams (tafaha's bug),
heading-level jumps (##→####), Arabic script outside markers / `{lang=ar}` spans (untranslated
remnant), sun-letter transliteration drift (`as-S…`, `ar-R…` vs house `al-`), unbalanced «»,
U+FFFD, glossed terms absent from the glossary, and a per-chunk completeness ratio — English
words ÷ source-page chars (manifest) — flagging chunks < 0.7 × book median (possible silent
omission). **Tests:** one fixture per check (~12 tests).

### T8 — Dataset pinning + checksums (supply-chain trust; do before T6/T7 docs)
Resolve the current exact fawazahmed0 release via the jsDelivr data API and hard-pin `_CDN`
(e.g. `@1.x.y`, no floating major). `setup_data.py` writes `data/MANIFEST.json` (tracked):
per file `{url, sha256, bytes, fetched_at}`; `--check` re-hashes local files against it (exit 1
on mismatch). Baseline manifest generated from the EXISTING local files — the corpus all four
books were verified against. surah_names.json included.
**Tests:** download writes manifest (fake fetch); `--check` catches tamper; skip-existing
preserves entries.

### T9 — Ingest speed
`analyze_book`: one whole-document `pdftotext` call split on form-feeds (page-count checked
against `pdfinfo`; mismatch falls back to per-page). `pdffonts` stays per-page. Halves
subprocess count for a 272-page book. **Tests:** fake-run fixture asserting one text call +
correct per-page counts; fallback path.

### T6 — Reviser pass (the missing prose QA; TEP "edit" stage)
New `templates/reviser-subagent.md`. Inputs: PDF path, page range, chunk file path, glossary,
DISPATCH.md. Sweeps: (1) completeness page-by-page against the images; (2) fidelity — meaning
errors, negations, numbers, names; (3) conventions — glossary/honorifics/heading levels/labels/
footnotes/poetry; (4) marker hygiene by SHAPE only. **Hard rule: never rewrite text inside
`<!--quran/hadith-->` bodies — flag, don't touch (verify owns wording).** Minor fixes: edit the
chunk file directly, log each one-line. Majors (missing paragraph/page, systematic
mistranslation): don't attempt; report for re-dispatch (one re-translate → re-revise round max).
Returns a SHORT status (edits applied, majors, flags). SKILL step 5b: revisers run under the
same wave + usage-gate discipline; Sonnet-class is sufficient (reading-heavy); "quick draft"
runs may skip 5b explicitly. No pipeline code.

### T7 — Truth-sync: template, SKILL, README
`templates/translator-subagent.md`: output contract becomes WRITE `chunk_NNNN.md` then return a
short flag-status (the cutoff-proven pattern — write before self-check); isnad→matn marker rule;
opening-Basmala rule; enumeration-labels-as-bold-run-ins note; mutashabihat rule (T3); `--prefer`
usage (T2); `nearest` retry etiquette; `english_warning` → flag. `SKILL.md`: step 0 (cd repo +
`.venv`); step 5 includes authoring a per-book `DISPATCH.md` (book-specific conventions layer —
currently undocumented); step 5b revise; verify step also runs `out.lint`; harvest step adds
English-fix proposals; install section (symlink into `~/.claude/skills/`). `README.md`: pipeline
diagram gains the revise + lint stages; document english-fixes governance, cache, pinning,
platform notes (macOS-tested; Linux font/Chrome pointers), skill install, quickstart.
**Acceptance:** no contradiction across SKILL.md / both templates / README / DISPATCH practice.

### T10 — Public-release readiness
`LICENSE` = MIT (code only; README's scoping note already correct — update its "no license yet"
section). Font attribution: confirm `assets/fonts/OFL.txt` covers Amiri AND Cardo copyright
lines; add per-family notices if not. Minimal `.github/workflows/tests.yml` (pytest,
`-m "not integration"`, no dataset downloads). Hygiene: re-scan tracked files + full history for
personal data / absolute paths / book content (today's scan: clean; nothing from `runs/` or
datasets ever committed). Surface to the user, decision theirs: personal email in git history
(`24418997+mohamad-kayal@users.noreply.github.com`) — keep, or rewrite history / switch to a noreply email before first
push. `render_pdf.py`: verify Chrome discovery is overridable (env/flag) for non-macOS.

### T11 — Ship checks
Full suite green; `out.verify` re-run on all four books (expect: 0 problems, same flags + new
U+FFFD flags where dataset English is dirty); `out.lint` run on all four books (report signal,
do NOT edit shipped books); install the skill symlink; self-review the whole diff for
correctness + simplification; commits per task; memory updated. Publishing (remote + push)
NOT included — explicit user authorization required.

## Order

T1 → T2 → T3 → T4 → T5 → T8 → T9 (code, TDD) → T6 → T7 (docs describe real behavior) →
T10 → T11. Commits land per task on `main` (project convention; push remains opt-in).

## Out of scope

Running the staged fadail book (separate decision — do it AFTER these fixes; it benefits most);
DOCX footers (no local Word to verify); OCR ingest for scanned books (no such book yet);
resolving the open review.md sign-off items (user decisions, not pipeline work).
