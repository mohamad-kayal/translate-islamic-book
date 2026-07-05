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

## Per book
1. **Ingest.** `python -m scripts.ingest_book analyze <book.pdf> --work <book>/work` → note
   `total_pages`, `toc_candidate_pages`, `ornamental_pages`.
2. **Read the ToC (vision).** Read the ToC page(s) with the Read tool and write
   `<book>/work/structure.json`:
   `[{"title": "...", "start_page": N, "level": 1, "appendix": false}, ...]`
   (mark appendix chapters `"appendix": true`).
3. **Chunk.** `python -m scripts.ingest_book chunk <book.pdf> --work <book>/work --target 10`
   → `<book>/work/chunks.json`.
4. **Prime the glossary.** Read ~3 spread-out chunks; write `<book>/work/glossary.json` — canonical
   English for recurring names and transliterated terms (with their parenthetical glosses).
5. **Translate (parallel subagents).** For each chunk, dispatch a Task subagent with
   `templates/translator-subagent.md`, the chunk's page range + `context_page`, the glossary, and whether
   it is an appendix chunk. Save each subagent's Markdown to `<book>/work/translated/chunk_NNNN.md`.
   Run up to ~8 concurrently.
6. **Verify.** `python -m out.verify` over the translated chunks; collect `problems` (fix by re-running
   that chunk) and `flagged` items → write `<book>/work/review.md` for the user.
7. **Assemble + convert.** `python -m out.assemble <book>/work/translated <book>/work/book.md`, then
   `python -m out.convert <book>/work/book.md <book>/output`.
8. **Report.** Give the user `output/<book>.docx`, `output/<book>.html`, and `review.md` (the hadith to
   sign off on). For PDF: export from Word, or open the HTML in a browser and print to PDF — both render
   Arabic correctly.

## Non-negotiables
- Verse/hadith text is ALWAYS from the retrieval library or a flagged fallback — never LLM-written.
- Never split a section across chunks (the chunker enforces this).
- Nothing in `review.md` is altered without the user's sign-off.
