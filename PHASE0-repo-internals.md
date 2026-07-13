# Phase 0 — Verified internals of translate-islamic-book

Verified 2026-07-13 against the local repo at `~/Documents/Translations/translate-islamic-book`
(published: https://github.com/mohamad-kayal/translate-islamic-book). This corrects the research
plan's inferences; **code against this, not the plan's guessed schema.**

## 1. Master glossary schema — `data/glossary.json` (ACTUAL)

```json
{
  "style": "al- (no sun-letter assimilation); ' for ayn/hamza; no macrons; first use: *translit* ([ARABIC]{lang=ar dir=rtl}, english), short form after",
  "terms":     { "التوحيد": {"translit": "tawhid", "english": "the Oneness of Allah"} },
  "names":     { "ابن تيمية": "Ibn Taymiyyah" },
  "structure": { "الباب": "Chapter", "القسم": "Part", "المطلب": "Section" }
}
```

Differences from the plan's inferred schema:

- **`style` is a top-level free-text string** stating transliteration + gloss conventions. There is
  no `meta` block, no version field.
- **No `book` block in the master.** Per-book glossaries (`runs/<slug>/work/glossary.json`) add it:
  `{"title_ar", "title_en", "subtitle_ar", "subtitle_en", "author_ar", "author_en"}`.
- **`terms` entries have exactly two fields**: `translit`, `english`. No `alt`/`notes`/`pos`/
  `status`/`sources`/`locked`. "Locking" is procedural (human-gated merge), not a data field.
- **`names` values are plain strings**, not objects — e.g. `"النبي": "the Prophet ﷺ"`.
- **`structure` maps Arabic heading words to English LABELS** ("Part"/"Chapter"/"Section"), **not**
  markdown levels. The heading-level map (chapter=`##`, section=`###`) lives in the translator
  template + per-book DISPATCH.md.
- **No `honorifics` section.** Honorific rules are conventions in the translator template
  (ﷺ kept verbatim, عليه السلام → "(peace be upon him)").
- Per-book glossaries may add **`works`** (cited-work Arabic title → transliteration string, e.g.
  `"حجية السنة": "Hujjiyyat al-Sunnah"`). `out/lint.py:84` reads it for drift checks; the
  back-of-book appendix reads `terms` only.
- **`override`** is an extra key inside a term's dict value (`"override": "<reason>"`) marking a
  deliberate book-local deviation.

## 2. `scripts/glossary.py` — exact behavior

- `SECTIONS = ("terms", "names", "structure")` — diff/merge touch ONLY these three. `style`,
  `book`, `works` never merge into the master.
- `diff(master, book)` returns `{"new_terms": {}, "new_names": {}, "new_structure": {},
  "conflicts": []}`. Each conflict: `{"section", "arabic", "master", "book", "override": None}`.
- Entries carrying `override` are excluded from BOTH `new_*` and `conflicts` — so they can never
  be merged, even via `--only` (the plan said "never merged"; the mechanism is exclusion at diff
  time).
- `merge(master, book, only=None)`: applies `new_*` entries (restricted to `only` if given);
  conflicts apply ONLY when their Arabic key is named in `--only`; strips `override` keys on write.
  Writes master with `ensure_ascii=False, indent=2, sort_keys=True`.
- CLI: `python -m scripts.glossary diff|merge <book-glossary.json> [--master data/glossary.json]
  [--only arabic,arabic]`. Run from the repo root (`--master` default is relative). Stdlib only.

## 3. Translator template — the part that changes the SRT design

`templates/translator-subagent.md` confirms the pipeline's "backend" is **Claude Code subagents
dispatched with the Agent tool / Workflow**, not API adapters:

- Each subagent reads rendered PDF page images itself (Read tool), runs the `retrieval.*` lookup
  CLIs itself, **writes its own output file BEFORE its final self-check** (cutoff-safe), and
  returns only a short status + flags.
- Gloss convention (book prose): first use `*translit* ([ARABIC]{lang=ar dir=rtl}, english)`,
  short `*translit*` after. This is pandoc-flavored — an SRT pipeline needs a lighter convention
  (no `{lang=ar}` spans in subtitles).
- Sacred text: never generated — `retrieval.quran_lookup` / `retrieval.hadith_lookup --prefer
  <coll>`, verbatim paste into `<!--quran-->`/`<!--hadith-->` markers, `src=fallback conf=0` +
  flag when not bundled. "Citations follow the author; wording follows the dataset."
- Second reviser pass at scale runs as a **resumable Workflow**
  (`pipeline(chunks, reviseStage, fixMajorsStage)` with StructuredOutput schemas) — 236 chunks,
  0 lost. This is the proven orchestration to reuse for SRT batches.

**Implication:** the plan's `srt/backends/{claude,gpt,gemini,openrouter}.py` API-adapter layer is
NOT how the existing pipeline works. Two options (decision needed):
- **(A) SRT-as-skill** (matches proven architecture): Python does parse/batch/reassemble/lint;
  translation + revision are subagents dispatched by the orchestrating agent, glossary-subset
  injected into each subagent brief. No API keys, reuses pilot gate / usage gate / RESUME
  patterns as-is.
- **(B) Standalone API CLI** (matches the plan): runs outside Claude Code, needs keys + the
  backend layer, but is scriptable/croneable independently.

## 4. Other verified reusables

- Usage gate: `python -m scripts.run_status <work> --gate` (threshold 90, fail-open PAUSE/PROCEED;
  reads `~/.claude/usage-snapshot.json` teed by the installed statusline script).
- Orthography folding lives in `retrieval/normalize.py` (incl. `fix_kfgqpc_spaces`) — reuse for
  glossary key matching on dialect-ish SRT text.
- Repo state: 233+ tests green, Python 3.9+ stdlib-only pipeline, `.venv` + `python -m …` assume
  cwd = repo root.

## 5. Open decisions before Phase 1

1. **Where does the SRT code live?** The plan says `srt/` inside translate-islamic-book (shares
   `scripts/glossary.py` + `data/glossary.json` with zero plumbing). But this folder
   (`~/Documents/SRT-translator`) was created as a separate project. Separate repo would need the
   glossary path passed in (e.g. `--master ~/Documents/Translations/translate-islamic-book/data/glossary.json`)
   or a sync step. **Recommendation: sibling `srt/` package in the existing repo**, this folder for
   the editor web app (or nothing).
2. **Architecture (A) skill vs (B) API CLI** — see §3. **Recommendation: (A)**, matching the five
   shipped books' orchestration; (B) can be added later behind the same batch format if needed.
3. **Glossary extensions for SRT**: keep the master schema untouched; if SRT needs honorific
   expansion rules or a subtitle-specific gloss style, put them in the SRT template/DISPATCH
   convention (like the book pipeline does), not new JSON sections.
