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
4. **Prime the glossary.** Read ~3 spread-out chunks; write `<book>/work/glossary.json` — canonical
   English for recurring names and transliterated terms (with their parenthetical glosses).
5. **Translate (parallel subagents).** For each chunk in chunks.json, dispatch a Task subagent with
   `templates/translator-subagent.md`, the chunk's page range + `context_page`, its section titles,
   the glossary, and its `appendix` flag. Save each subagent's Markdown to
   `<book>/work/translated/chunk_NNNN.md`.
   - **Pilot gate**: run chunk 1 alone first, verify + read it, and only then fan out the rest
     (up to ~8 concurrently).
   - **Failure policy**: a subagent that dies or returns malformed output costs only its own chunk —
     re-dispatch that chunk alone. Save each result as soon as it arrives; never discard completed
     chunks because a sibling failed.
6. **Assemble.** `python -m out.assemble <book>/work/translated <book>/work/book.md
   --title "<English book title>" --author "<Author name>"`.
7. **Verify.** `python -m out.verify <book>/work/book.md` — checks marker refs AND that every
   quran/hadith Arabic body is verbatim dataset text. `problems` = fix (usually re-run that chunk);
   `flagged` (fallback-sourced or low-confidence items) = write into `<book>/work/review.md` for the
   user's sign-off. Include the verify JSON in review.md.
8. **Convert.** `python -m out.convert <book>/work/book.md <book>/output` → `book.docx` + `book.html`
   (title page, table of contents, book typography, embedded fonts).
9. **Report.** Give the user `output/book.docx`, `output/book.html`, and `review.md`. For PDF: open
   the HTML in a browser and print to PDF (chapters break onto new pages), or export from Word.

## Non-negotiables
- Verse/hadith text is ALWAYS from the retrieval library or a flagged fallback — never LLM-written,
  and `out.verify` enforces this against the datasets after assembly.
- Never split a section across chunks (the chunker enforces this, including same-page sections).
- Nothing in `review.md` is altered without the user's sign-off.
