---
name: translate-islamic-book
description: Translate an Arabic Islamic book (Quran + hadith + author prose) into English at high
  fidelity — sacred content is retrieved verbatim from bundled datasets (never LLM-written), the author's
  prose is translated by parallel subagents, and the result is assembled to DOCX + HTML. Use when the user
  wants to translate an Arabic religious / Islamic book PDF into English.
---

# Translate an Islamic book

## One-time setup
- `python scripts/setup_data.py` — downloads the Quran + hadith datasets into `data/`.
- Ensure `pandoc` and poppler (`pdftotext`, `pdfinfo`, `pdffonts`) are installed.
- Fonts for the DOCX (Word must have them installed): `cp assets/fonts/*.ttf ~/Library/Fonts/`
  (Cardo, Amiri, Amiri Quran — all OFL).
- **Usage gate (recommended):** `cp scripts/statusline_usage.py ~/.claude/` and add to
  `~/.claude/settings.json`: `"statusLine": {"type": "command", "command": "python3
  ~/.claude/statusline_usage.py"}`. This tees live usage percentages to
  `~/.claude/usage-snapshot.json` for the translate-step gate (and shows them in the terminal).
  Without it the gate degrades gracefully: runs proceed with a stated warning.

## Per book
1. **Ingest.** `python -m scripts.ingest_book analyze <book.pdf> --work <book>/work` → note
   `total_pages`, `toc_candidate_pages`, `ornamental_pages`.
2. **Read the ToC (vision).** Read ALL the ToC page(s) with the Read tool and write
   `<book>/work/structure.json`:
   `[{"title": "...", "start_page": N, "level": 1, "appendix": false}, ...]`
   - mark appendix chapters `"appendix": true`;
   - if the book ends with non-content back matter (notebook pages, fihris, publisher ads), add a
     final sentinel `{"title": "back matter", "start_page": N, "skip": true}` so it is never chunked;
   - spot-check 2–3 `start_page` values by reading those pages — a printed-vs-PDF page offset
     silently corrupts every chunk.
3. **Chunk.** `python -m scripts.ingest_book chunk <book.pdf> --work <book>/work --target 10`
   → `<book>/work/chunks.json`. Read the warnings it prints: uncovered pages must be intentional
   front matter, and a section starting on an ornamental page means your page numbers are off.
4. **Prime the glossary.** Copy the master to the book: `cp data/glossary.json <book>/work/glossary.json`.
   Add a `book` block (Arabic + English title/subtitle/author). Read ~3 spread-out chunks and ADD
   book-specific entries under `terms`/`names`/`structure` (keep the master's transliteration
   style). If this book deliberately renders a master term differently, add `"override": "<reason>"`
   to that entry — otherwise the harvest step will flag it as a conflict.
5. **Translate (parallel subagents).** For each chunk in chunks.json, dispatch a Task subagent with
   `templates/translator-subagent.md`, the chunk's page range + `context_page`, its section titles,
   the glossary, and its `appendix` flag. Save each subagent's Markdown to
   `<book>/work/translated/chunk_NNNN.md`.
   - **Usage gate**: before the pilot and before EVERY subsequent wave, run
     `python -m scripts.run_status <book>/work --gate` (`--threshold N` overrides the default
     90). On `PAUSE`: do not dispatch — write RESUME.md (see "Pausing and resuming a run"), tell
     the user the reset time, and stop cleanly. A degraded verdict states its reason and
     proceeds. The percentages printed at each wave show the burn per wave — mention them to the
     user when tuning `--threshold`.
   - **Pilot gate**: run chunk 1 alone first, verify + read it, and only then fan out the rest
     (up to ~8 concurrently).
   - **Failure policy**: a subagent that dies or returns malformed output costs only its own chunk —
     re-dispatch that chunk alone. Save each result as soon as it arrives; never discard completed
     chunks because a sibling failed.
6. **Assemble.** `python -m out.assemble <book>/work/translated <book>/work/book.md
   --title "<English book title>" --author "<Author name>" --glossary <book>/work/glossary.json`.
   This strips chunk-seam page notes, inserts ayah numbers into multi-verse Quran blocks from the
   dataset (and drops stray ۞ division marks), and numbers hadith. `--glossary` appends a back-of-book
   Glossary appendix (terms only). Add `--no-hadith-numbers` when the book cites hadith inline as
   evidence (the common case) rather than as a numbered collection.
7. **Verify.** `python -m out.verify <book>/work/book.md` — checks marker refs AND that every
   quran/hadith Arabic body is verbatim dataset text. `problems` = fix (usually re-run that chunk);
   `flagged` (fallback-sourced or low-confidence items) = write into `<book>/work/review.md` for the
   user's sign-off. Include the verify JSON in review.md.
8. **Harvest the glossary.** `python -m scripts.glossary diff <book>/work/glossary.json` lists this
   book's new terms and any conflicts with the master. Write them into `<book>/work/review.md` under
   a "Glossary proposals" heading for the user's sign-off. After sign-off, run
   `python -m scripts.glossary merge <book>/work/glossary.json` and commit the updated
   `data/glossary.json`. By default `merge` writes ONLY brand-new terms (Arabic keys absent from
   the master) — safe additions the proposals already showed. A conflict (an existing key whose
   book value differs) is never applied unless the user explicitly accepts it by naming its Arabic
   key: `merge <book>/work/glossary.json --only <arabic-keys>`. This book's `override` entries
   (deliberate book-local deviations) are NEVER merged into the master, with or without `--only`.
   Never merge before sign-off.
9. **Convert.** `python -m out.convert <book>/work/book.md <book>/output` → `book.docx` + `book.html`
   (title page, table of contents, book typography, embedded fonts).
10. **Report.** Give the user `output/book.docx`, `output/book.html`, and `review.md`. For PDF: open
    the HTML in a browser and print to PDF (chapters break onto new pages), or export from Word.

## Pausing and resuming a run

A run can stop early — usage-gate PAUSE, a crash, a closed session — and loses at most the
in-flight wave: completed chunks are already in `<book>/work/translated/`.

**On any early stop, write `<book>/RESUME.md`** from `python -m scripts.run_status <book>/work`
plus what only you know:

- Book title (Arabic + English) and the work dir.
- Chunk state: N done / M missing, listing the missing chunk numbers.
- The exact commands with their run-specific flags (`--target` used at chunk time,
  `--no-hadith-numbers` at assemble, …) and the glossary path.
- Which usage window tripped and its reset time (from the PAUSE verdict printed by the `--gate`
  run that triggered the stop, not the bare status command), when applicable.
- The one-line instruction for the user: "Resume the <book> run in <work dir>".

**To resume:** run `python -m scripts.run_status <book>/work`; confirm `structure.json` and
`glossary.json` exist; dispatch subagents for the MISSING chunks only (same template, same wave
discipline — the usage gate applies to resumed waves too); then continue from step 6 unchanged
(assemble reads whatever is in `translated/`). No `chunks.json` = nothing to resume; restart
from step 1 (the ingest steps are cheap).

## Non-negotiables
- Verse/hadith text is ALWAYS from the retrieval library or a flagged fallback — never LLM-written,
  and `out.verify` enforces this against the datasets after assembly.
- **Citations follow the author; wording follows the dataset.** The retrieval supplies the verbatim
  Arabic/English *wording*. Any *reference* — a hadith's collection/number, or a verse's surah:ayah —
  follows what the AUTHOR printed whenever it differs from the dataset (e.g. numbering editions
  differ). Keep the author's reference in the visible text; the marker keeps the dataset location so
  `out.verify` can confirm the wording.
- Never split a section across chunks (the chunker enforces this, including same-page sections).
- Nothing in `review.md` is altered without the user's sign-off.
- `review.md` is a per-book document: title it with the book, list that book's hadith and their
  sources, the verify summary, and any items (fallbacks, low-confidence, author/dataset citation
  differences, awkward dataset English) that need the user's sign-off.
