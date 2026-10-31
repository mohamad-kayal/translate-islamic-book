---
name: translate-islamic-book
description: Translate an Arabic Islamic book (Quran + hadith + author prose) into English at high
  fidelity — sacred content is retrieved verbatim from reference datasets and machine-checked, the
  author's prose is translated by parallel subagents, and the result is assembled to PDF + DOCX +
  HTML. Use when the user wants to translate an Arabic religious / Islamic book PDF into English.
---

# Translate an Islamic book

Run every command from the repo root (`cd "$(git -C "${CLAUDE_SKILL_DIR}" rev-parse --show-toplevel)"`;
other agents: resolve this file's real path, `<repo>/skills/<name>/SKILL.md`, and follow
`<repo>/AGENTS.md`), with `python` meaning `.venv/bin/python`. One book is
one run: `runs/<slug>/`, with `<work>` = `runs/<slug>/work`. First time here: `./install.sh`.

## Steps

1. **Ingest.** `python -m scripts.ingest_book analyze <book.pdf> --work <work>` → note
   `total_pages`, `toc_candidate_pages`, `ornamental_pages`.
2. **Read the ToC (vision).** Read ALL the ToC page(s) as images and write `<work>/structure.json`:
   `[{"title": "...", "start_page": N, "level": 1, "appendix": false}, ...]`
   - mark appendix chapters `"appendix": true`;
   - if the book ends with non-content back matter (notebook pages, fihris, publisher ads), add a
     final sentinel `{"title": "back matter", "start_page": N, "skip": true}` so it is never chunked;
   - spot-check 2–3 `start_page` values by reading those pages — a printed-vs-PDF page offset
     silently corrupts every chunk.
3. **Chunk.** `python -m scripts.ingest_book chunk <book.pdf> --work <work> --target 10` →
   `chunks.json`, then `python -m scripts.ingest_book assignments --work <work>` →
   `assignments.md`, one brief per chunk. Read the warnings: uncovered pages must be intentional
   front matter, and a section starting on an ornamental page means your page numbers are off.
4. **Prime the glossary.** `python -m scripts.glossary prime <work> --pdf <book.pdf>` writes
   `<work>/glossary.json`: the master's entries this book mentions, or the whole master for an
   image-only PDF. Fill its `book` block (`title_en`, `title_ar`, `author_en`, `author_ar`, and
   `translator`, `edition`, `year` for the copyright page). Read ~3 spread-out chunks and ADD
   book-specific entries under `terms`/`names`/`structure`, keeping the master's transliteration
   style. If this book deliberately renders a master term differently, add
   `"override": "<reason>"` to that entry, otherwise the harvest will flag it as a conflict.
5. **Write `<work>/DISPATCH.md`,** a one-page brief every subagent reads FIRST.
   `templates/book-translator.md` is the base spec; DISPATCH.md refines it for THIS book: the
   book's names (Arabic + English + author), the source PDF path, the structural heading map
   (`الباب` → `##`, `الفصل` → `###`, …), how the author presents hadith (isnad style, where the
   takhrij lives, and therefore what to pass as `--prefer`), enumeration-label handling, recurring
   formulae beyond the default honorifics, and the output contract (WRITE
   `translated/chunk_NNNN.md`, return a short flag-status). Read 2–3 content pages first so the
   brief reflects the book's actual habits.
6. **Translate (parallel subagents).** For each chunk, dispatch a subagent with
   `templates/book-translator.md` + `DISPATCH.md`, `assignments.md`, the glossary path, and its
   chunk number. Subagents WRITE their own chunk file (complete file BEFORE their self-check, so a
   cutoff loses nothing) and return a short flag-status.
   - **Pilot gate:** run chunk 1 alone first, verify + read it, and only then fan out the rest
     (up to ~8 concurrently).
   - **Usage gate:** before the pilot and before EVERY later wave, run
     `python -m scripts.run_status <work> --gate` (`--threshold N` overrides the default 90). On
     `PAUSE`: do not dispatch; write RESUME.md (see below), tell the user the reset time, and stop
     cleanly. A degraded verdict states its reason and proceeds.
   - **Failure policy:** a subagent that dies costs only its own chunk: its file is missing or
     truncated, so re-dispatch that chunk alone. Completed chunks are never discarded because a
     sibling failed. Collect every returned flag for review.md.
7. **Revise (parallel subagents, the prose QA pass).** For each chunk, dispatch a REVISER with
   `templates/book-reviser.md` + `DISPATCH.md`, the same chunk info, and the chunk file. Revisers
   re-read the source pages and check completeness page by page, fidelity (negations, numbers,
   names), conventions and marker shape; they fix minors in place and return an edits/majors/flags
   report. Same wave + usage-gate discipline as translation; a smaller model is fine here. Append
   each report to `<work>/revise-log.md`, which is this step's resume marker and feeds review.md.
   - A chunk reporting **majors** (missing paragraphs or pages, systematic mistranslation):
     re-dispatch the TRANSLATOR with the reviser's notes appended, then re-revise. One round only;
     if majors persist, put the chunk in review.md for the user.
   - Skip this step only when the user explicitly asks for a quick draft, and say so in review.md.
   - **At scale (a whole book or a batch), in Claude Code run this as a resumable Workflow**: a
     fleet of hand-launched background agents does not survive a session interruption, whereas a
     Workflow re-runs only what didn't finish. Pattern: `pipeline(chunks, reviseStage,
     fixMajorsStage)`, stage 1 a reviser per chunk with a structured
     `{slug,chunk,edits[],majors[],flags[]}` schema, stage 2 a translator only when `majors` is
     non-empty. Parse `args` defensively: `const A = typeof args === 'string' ? JSON.parse(args) : args`.
8. **Finish.** `python -m scripts.finish_book runs/<slug>` assembles, verifies, lints, converts and
   renders `output/<slug>.{pdf,docx,html}`; it refuses to render while problems remain. Add
   `--numbered` only when the book presents hadith as a numbered collection (the rare case).
   - Assembly strips chunk-seam page notes, inserts ayah numbers from the dataset, builds the
     cover, indexes and a glossary appendix of the terms the book actually uses.
   - **A hadith whose English is not verified dataset text gets a † automatically,** and the
     copyright page states how many. Do not add or remove these by hand.
   - `problems` must be fixed. `flagged` items and lint `warnings` go in review.md: variants, own
     renderings, low-confidence matches, dataset-English damage, possible omissions.
9. **Write `<work>/review.md`.** Title it with the book. List its hadith and their sources, the
   summaries from step 8, and everything needing the user's sign-off. Then:
   - **Glossary proposals:** `python -m scripts.glossary diff <work>/glossary.json` lists new
     entries and conflicts. After sign-off, `python -m scripts.glossary merge <work>/glossary.json`
     and commit. By default merge writes only brand-new terms; a conflict applies only when the
     user names its key with `--only <arabic-keys>`; `override` entries never merge.
   - **English-fix proposals:** dataset damage this run surfaced, as `data/english-fixes.json`
     entries. Never edit that file without sign-off.
10. **Gate.** `python -m scripts.gate runs/<slug>` must exit 0 before you call the book finished.
11. **Report.** Give the user `output/<slug>.pdf`, `.docx`, `.html` and `review.md`.

## Pausing and resuming

A run can stop early (usage PAUSE, a crash, a closed session) and loses at most the in-flight wave:
completed chunks are already in `<work>/translated/`.

**On any early stop, write `runs/<slug>/RESUME.md`** from `python -m scripts.run_status <work>` plus
what only you know: book title, N done / M missing with chunk numbers, the run-specific flags, which
usage window tripped and its reset time, and the one-line instruction "Resume the <book> run in
<work>".

**To resume:** run `python -m scripts.run_status <work>`; confirm `structure.json`, `glossary.json`
and `DISPATCH.md` exist; dispatch translators for the MISSING chunks only; revise every chunk not yet
in `revise-log.md`; continue from step 8. No `chunks.json` means nothing to resume: restart from
step 1, which is cheap.

## Non-negotiables

- Verse and hadith text comes from the retrieval library. A hadith outside the datasets keeps its
  Arabic as printed and is flagged and marked †. Never write scripture from memory.
- Every Qur'an block must carry the dataset's wording in both languages: `out.verify` fails the book
  otherwise.
- The author's prose gets an INDEPENDENT reviser pass before assembly: the translator never signs
  off its own work. Skipped only on the user's explicit quick-draft request, and review.md says so.
- A repeated Qur'anic phrase (`n_locations` > 1) is never cited from the lookup's first hit alone:
  the author's printed reference decides, else context, and the choice is flagged.
- **Citations follow the author; wording follows the dataset.** Any visible reference follows what
  the AUTHOR printed; the marker keeps the dataset location so `out.verify` can confirm the wording.
- Never split a section across chunks (the chunker enforces this, including same-page sections).
- Nothing in `review.md` is altered without the user's sign-off.
