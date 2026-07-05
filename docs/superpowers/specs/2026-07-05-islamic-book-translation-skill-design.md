# Design Spec — `translate-islamic-book` Skill

**Date:** 2026-07-05
**Status:** Draft for user review
**Author:** Claude (brainstormed with user)

---

## 1. Purpose & Goals

A reusable Claude Code skill that translates **Arabic Islamic religious books into English** at the
highest attainable fidelity, matching the methodology and formatting the user already established in
their hand-produced translation of *Al-Minhaj min Mirath an-Nubuwwah*.

The defining constraint: **sacred content is never translated by the model.** Quranic verses and
Prophetic hadith are *retrieved verbatim* from bundled authoritative sources. Only the author's own
prose is genuinely translated by the LLM. This eliminates the single failure mode the user cares most
about — a model paraphrasing scripture from memory.

**Success criteria:**
- Every Quran verse in the output is the exact bundled Saheeh International (or Clear Quran) text, with a correct `[Surah: ayah]` reference.
- Every hadith is the exact bundled sunnah.com rendering with a correct `(Narrated by …)` citation.
- Author prose reads as clear, faithful English in the user's established tone.
- Structure, highlighting conventions, transliteration glosses, and ﷺ usage match the existing *Al-Minhaj* translation.
- On the *Al-Minhaj* benchmark, the skill's retrieved verses/hadith and references match the user's own translation.

## 2. Scope & Non-Goals

**In scope:** Arabic→English; digital (text-bearing) PDFs of Islamic books containing author prose +
Quran + hadith, with a table of contents; books that are prose-heavy or quotation-heavy; ornamental /
calligraphic pages.

**Non-goals (v1):**
- Languages other than Arabic→English.
- Scanned/image-only books requiring full OCR (we handle *occasional* zero-text ornamental pages via vision, not whole scanned volumes).
- Automated print-grade typesetting (we produce an editable DOCX + a PDF preview; final book layout stays the user's manual step, as today).
- Publishing/redistribution workflows (licensing of bundled translations is a personal-use assumption — see §12).

## 3. Core Principle — Three Translation Lanes

Every span of source content is routed to exactly one lane:

| Lane | Source content | What the model does | Output |
|------|----------------|---------------------|--------|
| **Prose** | Author's introductions, chapter titles, commentary, connective text | **Translates** — literal and faithful to tone, with light de-ambiguation for clarity; never adds or omits meaning | English prose |
| **Quran** | Quranic verse(s), often multi-ayah ranges | **Matches & retrieves** — identifies the surah:ayah span, pulls canonical text | Arabic (canonical) + `[السورة: N]` + Saheeh Intl English + `[Surah: ayah]` |
| **Hadith** | Prophetic narration | **Matches & retrieves** — identifies collection + number, pulls canonical text | Arabic + `« … »` + English + `(Narrated by …, N)` |

The LLM still drives the whole pipeline — it reads each page and *decides* which lane each span
belongs to. It is a translator for prose and a librarian for scripture.

## 4. Inputs & Outputs

**Input:** one Arabic PDF (text-bearing). Optional: a config overriding chunk size, concurrency,
Quran translation preference (Saheeh Intl default), output formats.

**Output** (in `<book>/output/`):
- `<book>.md` — canonical structured translation (source of truth, re-runnable/diffable).
- `<book>.docx` — editable Word document styled like the user's draft.
- `<book>.pdf` — preview (Arabic-capable fonts embedded).
- `review.md` — hadith/ambiguities flagged for user sign-off + any dataset-miss fallbacks.

## 5. Architecture — Six-Stage Pipeline

Principle (borrowed from the `deusyu/translate-book` skill): **scripts do bookkeeping; the LLM does
meaning.** Deterministic Python owns extraction, hashing, matching, and assembly; subagents own prose
translation and lane routing.

```
Stage 1  Extract & Classify   (script + vision fallback)
Stage 2  Map Structure        (script, LLM-assisted ToC parse)
Stage 3  Smart Chunk          (script)
Stage 4  Translate  ── parallel Task subagents ──   (LLM + dataset lookup)
Stage 5  Verify                (script checks + verify subagent)
Stage 6  Assemble & Convert    (script)
```

### Stage 1 — Extract & Classify
`scripts/extract.py`: per page, extract text (`pdftotext -enc UTF-8 -layout`), record char count,
detect Quran typography (KFGQPC Uthmanic font / ayah-marker glyphs), and **classify each page**:
- `text` — normal extractable page.
- `ornamental` — near-zero text, vector calligraphy (e.g., a Basmala or divider). Rendered to an
  image and read by a vision-capable subagent, which returns either a short semantic note
  (`[Ornamental: Basmala — "In the name of Allah…"]`) or plain text if the calligraphy encodes a verse.
- `mixed` — has text but also significant zero-text regions → flagged for vision assist.

Output: `work/manifest.json` (page → {chars, classification, font-signals, sha256}).

### Stage 2 — Map Structure
`scripts/structure.py` locates the ToC pages, and an LLM pass parses them into a **section tree** with
page ranges (title, level, start page, end page). Falls back to heading detection (bold/known fonts,
"الباب"/"الفصل"/"المقطع"/"أولاً" markers) if no usable ToC. Output: `work/structure.json`.

### Stage 3 — Smart Chunk
`scripts/chunk.py` packs pages into chunks that **never split a section**: greedily fill a chunk up to
a soft target (default ~10 pages / ~6,000 source chars) but always cut on a section boundary from
`structure.json`. A section larger than the target becomes its own (larger) chunk rather than being
split mid-idea. Each chunk records its section list, page range, extracted source text, and a
~300-char tail excerpt of the previous chunk for cross-boundary continuity. Output:
`work/chunks/chunk_NNNN.json` + `work/run_state.json` (status per chunk).

### Stage 4 — Translate (parallel subagents)
A **glossary-priming pass** first samples a few chunks (first, middle, last) to build
`work/glossary.json` — canonical renderings of names (Ibrahim, Musa), transliterated terms
(*Tazkiyah*, *Da'wah*) with their parenthetical glosses, and recurring phrases. The main agent owns
glossary writes; subagents read it.

Then up to **K parallel Task subagents** (default 8) each translate one chunk using
`templates/translator-subagent.md`, receiving: the chunk source, the glossary, the previous-chunk tail
excerpt, and the lane rules (§3, §11). For each detected verse/hadith the subagent calls the lookup
scripts rather than writing scripture itself:
- `scripts/quran_lookup.py` → exact ayah-range retrieval.
- `scripts/hadith_lookup.py` → fuzzy-match narration → collection + number + English.

Each subagent outputs `work/translated/chunk_NNNN.md` + `chunk_NNNN.meta.json` (verse/hadith IDs used,
confidence, fallbacks, flagged ambiguities).

### Stage 5 — Verify
`scripts/verify.py` runs automated checks (§10); a **verify subagent** re-reads each chunk against its
source for coverage and lane-routing errors. Flagged hadith and dataset-misses are collected into
`review.md`. Failures mark the chunk for re-translation in `run_state.json`.

### Stage 6 — Assemble & Convert
`scripts/assemble.py` merges chunks in order into `<book>.md`, assigning the running **hadith numbers**
(main text sequential; appendix entries suffixed `-A`). `scripts/convert.py` uses pandoc to produce
DOCX and a PDF preview with Arabic-capable fonts.

## 6. Data Model — Working Artifacts

```
<book>/
  source.pdf
  work/
    manifest.json        # page classification, fonts, hashes
    structure.json       # section tree with page ranges
    chunks/chunk_NNNN.json
    glossary.json        # canonical terms/names/glosses
    translated/chunk_NNNN.md
    translated/chunk_NNNN.meta.json
    run_state.json       # per-chunk status, source hash, glossary version
    review.md            # flagged items for user sign-off
  output/
    <book>.md  <book>.docx  <book>.pdf
```

`run_state.json` enables **resumability**: a re-run redoes only chunks whose source hash changed,
whose glossary version changed, or that failed/were flagged — everything else is reused from cache.

## 7. Bundled Datasets

Stored under `data/`. **Sources verified live 2026-07-05** — the `fawazahmed0` **quran-api** and
**hadith-api** on jsDelivr, both under the **Unlicense** (public-domain dedication), pinned to major
version `@1`. A setup script downloads the needed full editions locally once.

- **Quran** (per-ayah schema `{chapter, verse, text}`; full file `{"quran":[…]}`): `ara-quranuthmanihaf`
  (Uthmani Hafs — the reference Arabic), **`eng-ummmuhammad` = Saheeh International** (verified against the
  user's An-Nisa 59 rendering), **`eng-mustafakhattaba` = The Clear Quran** (Allah edition, matching the
  user's book). Verse **matching folds orthography** (Uthmani ↔ Imlā'ī) by removing alefs from the match
  key, so a book in either spelling resolves against this one edition (verified necessary on real data —
  the target books differ: Al-Minhaj is Imlā'ī, Anwar al-Anbiya is Uthmani).
- **Hadith** (schema `{metadata, hadiths:[{hadithnumber, arabicnumber, text, grades, reference:{book,hadith}}]}`;
  Arabic & English editions join on `hadithnumber`): `ara-`/`eng-` for **bukhari, muslim, abudawud,
  tirmidhi, nasai, ibnmajah** (the Six Books), **malik** (Muwatta), and **nawawi / qudsi / dehlawi**
  (the "Forty" collections).
- **Coverage gap (verified):** **Musnad Ahmad, al-Hakim (Mustadrak), al-Bayhaqi, ad-Darimi, at-Tabarani
  are NOT in this dataset.** Narrations from these — and any matn that fails to match with sufficient
  confidence — take the **fallback path** (web lookup / careful LLM) and are flagged in `review.md`.
  *Al-Minhaj* draws its majority from the Sahihayn, so bundled coverage is high; the tail is handled by
  review, never invented.
- **Numbering caveat (verified):** collection numbering is source-dependent. Bukhari numbers align with
  the user's citations (Bukhari 79 = the rain/guidance hadith ✓), but this dataset's continuous **Muslim**
  numbering diverges from the Abdul-Baqi / sunnah.com numbers the user cites (its `2408` ≠ the user's
  "Muslim 2408"). Hence matching is by **Arabic matn, not number** (§8), and the printed citation follows
  the **author's own takhrij in the source**, with the dataset number used only to verify and flag
  divergences.

All datasets are local → offline, fast, reproducible at translation time. Attributions ("Saheeh
International", "Narrated by …") are surfaced in the output, as in the user's existing book.

> **Saheeh Intl typography note:** this copy renders plain "Allah/Muhammad"; the user's *Al-Minhaj* uses
> the official diacritical "Allāh/Muḥammad". An optional post-process can restore the diacritical forms —
> decided during implementation, not blocking.

## 8. Matching Strategy

**Quran (exact, deterministic):** normalize Arabic (strip tashkeel by Unicode category; normalize
alif/hamza/ya/ta-marbuta variants) and, to bridge **Uthmani vs Imlā'ī orthography**, remove alefs from the
**match key** (verified necessary on real data). Locate the query as a **substring** of the per-surah
match-key corpus — this resolves exact ayat, multi-ayah ranges, **and partial/mid-ayah quotations** (the
source often quotes only part of an ayah) — then map the character span back to the **start→end ayah
range**. Retrieve reference + Saheeh Intl (+ Clear Quran). If the source's extracted Arabic is noisy, the
**canonical dataset Arabic is authoritative** for what gets printed.

**Hadith (fuzzy, verified):** normalize and strip the isnad; match the *matn* against the hadith DB
using token-set / n-gram similarity; return the best-matching entry with a **confidence score**.
**Citation policy:** the printed reference follows the **author's own takhrij in the source** (the
collection + number the author cites); the dataset's number is used only to *verify* and is **flagged in
`review.md` on divergence** — numbering schemes differ across sources (§7: dataset Bukhari aligns with the
user's citations, dataset Muslim does not). If confidence < threshold or no match → **fallback** (web
lookup / careful LLM) **and flag** in `review.md`. Never silently invent.

The Arabic **printed** for a hadith is the author's quoted matn (the author may deliberately quote only a
portion), verified against the matched dataset entry; the dataset supplies the reference + English. If the
source Arabic is unreliable (extraction noise), the dataset's canonical matn for the matched span is used.

## 9. Formatting Conventions (match existing *Al-Minhaj* translation)

- **Chapter/section title:** heading (bold in DOCX), preserving the descriptive form ("Chapter One: A Chapter on …").
- **Quran verse:** Arabic in parentheses `( … )`, RTL; Arabic ref `[السورة: ٥٩]`; then the **Saheeh International** English in quotes + transliterated `[Surah: ayah]`. Lead-in prose ("Allah the Exalted said:") kept.
- **Hadith:** numbered; isnad lead-in ("On the authority of …, that the Prophet ﷺ said:"); Arabic in guillemets `« … »`; English in quotes + `(Narrated by Al-Bukhari 79, and Muslim 2282)`.
- **Transliterated terms:** `*Term* (gloss)` on first use — *Da'wah (calling to Islam)*, *Tazkiyah (purification of the soul)*.
- **ﷺ** preserved (U+FDFA) wherever the source has it.
- **Hadith numbering:** main text sequential (`1.`), appendix suffixed (`1-A`).
- Source page-number artifacts (`-8-`) are dropped; pagination is regenerated on convert.

## 10. Quality Control

Automated (`verify.py`):
- **Coverage:** every section from `structure.json` present; no empty chunk; page count reconciled.
- **Sacred integrity:** every verse/hadith in the output resolves to a dataset entry, verbatim. Non-matches listed.
- **Reference well-formedness:** surah names + ayah numbers valid and in range; hadith collection + number valid.
- **Consistency:** glossary terms/names rendered uniformly; ﷺ present where the source marked it.

Human-in-the-loop:
- **`review.md`** aggregates: (a) hadith whose canonical English is unclear/misreadable — inserted verbatim but flagged with a suggested clearer wording + reason, for the user's sign-off (the user's chosen policy); (b) any fallback-sourced or low-confidence sacred content.

Nothing sacred is altered without the user's approval.

## 11. Translation Rules (subagent contract)

The subagent template encodes, verbatim, the user's preface methodology:
1. **Prose** — literal, faithful to the author's intent and tone; light modification only to remove ambiguity / increase clarity; add nothing, omit nothing.
2. **Quran** — do not translate; retrieve via `quran_lookup.py`; present source Arabic (verified against, and if noisy replaced by, the canonical Uthmani text) + both-script references + **Saheeh International** English. Saheeh Intl is the deterministic default for *every* verse; The Clear Quran is **never silently substituted** — where it would materially aid clarity, the verse is inserted as Saheeh Intl and **flagged in `review.md`** with the Clear Quran alternative for the user to choose (matching how the user worked in *Al-Minhaj*).
3. **Hadith** — do not translate; retrieve via `hadith_lookup.py`; present Arabic + English + `(Narrated by …)`; apply numbering; flag-don't-alter on ambiguity.
4. **Humility** — where a term is genuinely untranslatable, transliterate + gloss rather than approximate.

## 12. Skill Layout & Licensing

```
translate-islamic-book/
  SKILL.md                     # workflow the main agent follows
  scripts/  (extract, structure, chunk, quran_lookup, hadith_lookup, verify, assemble, convert)
  data/     (quran/, hadith/)  # bundled datasets
  templates/ (translator-subagent.md, glossary-schema.json)
  docs/     (this spec, README)
  tests/    (unit + golden benchmark)
```

**Licensing note:** Quran Arabic is public domain; Saheeh International, The Clear Quran, and sunnah.com
renderings are third-party works bundled for **personal use**, with attributions surfaced in output.
Revisit before any public redistribution of generated books.

## 13. Testing Strategy

- **Golden benchmark (*Al-Minhaj*):** we already have the user's own English translation. Run the skill on the Arabic source and compare: do our retrieved verses/hadith and references match the user's? Structural parity? Prose measured by semantic similarity, not exact wording.
- **Generality smoke test (*Anwar al-Anbiya*):** run the first two sections; confirm multi-ayah retrieval, long-prose handling, and ornamental-page classification (the Basmala on p4) all work.
- **Unit tests:** `quran_lookup` (known single + range ayat), `hadith_lookup` (known Sahihayn narrations + a deliberately-unmatchable one → fallback path), `chunk.py` (asserts no section is split), `extract.py` (classifies p4 of *Anwar* as ornamental).

## 14. Error Handling & Resumability

- Subagent failure → retry (default 2) → mark failed, continue, surface in final report.
- Dataset miss → fallback path + `review.md` flag; never a silent invention.
- All state in `run_state.json` with source hashes → interrupted/edited runs resume, redoing only what changed.

## 15. Open Questions / Future

- **Very large books:** optionally swap Stage 4/5 fan-out to a deterministic `Workflow` engine (auto-resumable, per-chunk cached) if Task-subagent dispatch proves fiddly at 100+ pages.
- Additional Quran translations; footnote/endnote system; EPUB output; a second human-review UI.

---

## Decisions locked (from brainstorming)

- Sacred content: **bundled datasets primary**, web/LLM **fallback only**, fallbacks flagged.
- Output: **Markdown → DOCX + PDF**.
- Hadith ambiguity: **keep canonical + flag to `review.md` for sign-off**.
- Parallel engine: **Skill + Task subagents** (Workflow deferred to "future").
- Target: Arabic Islamic books with Quran + hadith + chapters; must tolerate prose-heavy books and ornamental pages.
