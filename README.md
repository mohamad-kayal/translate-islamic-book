# translate-islamic-book

A pipeline for translating Arabic Islamic books into **publication-grade English** — built so that
the sacred text is never at the mercy of a language model.

> **Core principle:** Qur'anic verses and hadith are **retrieved verbatim** from bundled reference
> datasets and **machine-verified** against them after assembly. Only the *author's own prose* is
> translated. The model never writes a verse or a hadith from memory.

It runs as a [Claude Code](https://claude.com/claude-code) skill (see [`SKILL.md`](SKILL.md)): the
orchestrating agent walks a fixed pipeline, dispatches parallel translator subagents for the prose,
and the Python tooling in this repo does the retrieval, verification, assembly, and typesetting.

---

## Why this exists

Machine translation of religious texts has an integrity problem: an LLM asked to "translate this
verse" will happily produce a fluent paraphrase that is *not* the received wording. For scripture
that is unacceptable. This project splits every span of the source into three lanes:

| Lane | Handling |
|---|---|
| **Qur'an** | Looked up in a verse dataset; the exact Arabic + an established English translation are pasted in. Never generated. |
| **Hadith** | Looked up in a hadith dataset by matn (with orthography-folded matching); exact wording pasted in. Never generated. Unmatched narrations become a **flagged fallback**, not an invention. |
| **Author's prose** | Translated by the model, faithfully and consistently. |

After the book is assembled, `out.verify` re-reads every quotation and confirms its Arabic body is
**byte-for-byte** the dataset text (or a transparently flagged near-verbatim variant). Anything that
doesn't check out is surfaced for human sign-off — it is never silently shipped.

A companion rule keeps scholarship honest: **citations follow the author, wording follows the
dataset.** If the author printed a different collection/number (numbering editions differ), the
*visible* reference is the author's; the retrieval only supplies the verbatim *wording*.

## What you get

Each translated book is produced as a self-contained **HTML** file (print to PDF) and an editable
**DOCX**, with a book-grade interior:

- A typographic **cover** and front matter (half-title, copyright/edition page with a sacred-text
  sourcing note).
- Chapter openings set as events (rubricated titles, drop capitals), a proper **Table of Contents**,
  and page folios in print.
- Qur'an set centered in a mushaf face; hadith set as distinct quotations — distinguished by
  *setting*, never by boxes.
- A back-of-book **Glossary** of transliterated terms and **indexes** of every Qur'anic verse and
  hadith cited, plus the author's endnotes.
- A per-book **`review.md`** listing every citation and every item that needs human sign-off
  (fallbacks, low-confidence matches, author-vs-dataset differences).

Typesetting is classical (Cardo for English, Amiri / Amiri Quran for Arabic), inline black + a single
rubric red — the aesthetic of a serious religious publisher's hardcover.

## How it works

```
PDF ──▶ ingest ──▶ (agent reads ToC) ──▶ chunk ──▶ translate (parallel subagents)
                                                        │  Qur'an ─▶ retrieval/quran_lookup
                                                        │  hadith ─▶ retrieval/hadith_lookup
                                                        ▼
                            assemble ──▶ verify ──▶ convert ──▶ HTML + DOCX  (+ review.md)
```

The full step-by-step workflow the agent follows lives in [`SKILL.md`](SKILL.md).

## Repository layout

```
retrieval/     Qur'an + hadith lookup, Arabic orthography normalization
ingest/        PDF page classification, structure, and section-aware chunking
out/           assemble (merge + number), verify (integrity check), convert (HTML/DOCX)
scripts/       data download, ingest CLI, glossary diff/merge, run-status gate, docx builder
templates/     the translator-subagent brief + the DOCX reference template
data/          the master glossary (datasets are downloaded here, not committed)
assets/        embedded OFL fonts
tests/         pytest suite (retrieval, ingest, assembly, verification, conversion)
SKILL.md       the pipeline the orchestrating agent runs
```

## Setup

Requirements: **Python 3.9+**, [`pandoc`](https://pandoc.org), and
[`poppler`](https://poppler.freedesktop.org) (`pdftotext`, `pdfinfo`, `pdffonts`).

```bash
python scripts/setup_data.py     # downloads the Qur'an + hadith datasets into data/
pip install -r requirements-dev.txt   # (tests only)
pytest -m "not integration"
```

Then follow [`SKILL.md`](SKILL.md) to run a book through the pipeline. In outline:

```bash
python -m scripts.ingest_book analyze <book.pdf> --work <book>/work
# (the agent reads the ToC pages and writes structure.json)
python -m scripts.ingest_book chunk   <book.pdf> --work <book>/work --target 10
# (translator subagents write <book>/work/translated/chunk_NNNN.md)
python -m out.assemble <book>/work/translated <book>/work/book.md --glossary <book>/work/glossary.json --indexes --matter
python -m out.verify   <book>/work/book.md
python -m out.convert  <book>/work/book.md <book>/output
```

## Data sources & credits

This tool *uses* third-party reference data and fonts; it does not redistribute them (datasets are
downloaded at setup, not committed):

- **Qur'an & hadith text/translations** — fetched via the public
  [`fawazahmed0/quran-api`](https://github.com/fawazahmed0/quran-api) and
  [`hadith-api`](https://github.com/fawazahmed0/hadith-api) (API code released under The Unlicense).
  English Qur'an renderings include **Saheeh International** and **The Clear Quran**; hadith are given
  in their published English translations.
- **Fonts** — [Cardo](https://scholarsfonts.net/cardofnt.html),
  [Amiri](https://github.com/alif-type/amiri), and Amiri Quran, all under the SIL Open Font License.
- **Tooling** — [pandoc](https://pandoc.org) and [poppler](https://poppler.freedesktop.org).

> ⚠️ **Please note:** the Qur'an and hadith **English translations** retrieved by this tool are the
> copyrighted work of their respective publishers. This repository contains no scripture text or
> translations — only code that fetches and typesets them. You are responsible for complying with the
> licensing terms of any translation you use, and for respecting the copyright of any source book you
> translate. Sacred texts should be reviewed by a qualified person before publication; the machine
> verification here guards *fidelity to the dataset*, not scholarly or theological correctness.

## License

No license is set yet. Before publishing, add a `LICENSE` file for the **code** — a permissive
license such as [MIT](https://choosealicense.com/licenses/mit/) is a sensible default for a tool
like this — and update this section. Whatever you choose applies only to the code here; it does
**not** extend to the datasets, translations, fonts, or any source book processed with it, which
retain their own licenses as noted above.
