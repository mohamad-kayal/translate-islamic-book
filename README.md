# translate-islamic-book

Translate Arabic Islamic books, lectures and social posts into **publication-grade English**, built
so that the sacred text is never at the mercy of a language model.

> **Core principle:** Qur'anic verses and hadith are **retrieved** from reference datasets and
> **machine-checked** against them, in Arabic and in English. Only the author's or speaker's own
> words are translated. A hadith that cannot be verified is marked in the output, never passed off
> as verified.

It runs as a set of skills for [Claude Code](https://claude.com/claude-code). An orchestrating agent
walks a fixed pipeline, translators and revisers handle the prose, and the Python here does the
retrieval, verification, assembly and typesetting. Other coding agents can run it the same way: see
[`AGENTS.md`](AGENTS.md).

| Give it | You get |
|---|---|
| An Arabic book PDF | A typeset book as PDF, DOCX and HTML, plus `review.md` |
| A YouTube link or `.srt`/`.vtt` | English subtitles (`.en.srt`), a bilingual proof and `review.md` |
| A post, quote card, link or a few paragraphs | Ready-to-post text, split into a thread if needed |

---

## Install

Requirements: Python 3.9+ (3.10+ recommended, so `yt-dlp` stays current),
[`pandoc`](https://pandoc.org), [`poppler`](https://poppler.freedesktop.org) and Chrome/Chromium.

```bash
git clone https://github.com/mohamad-kayal/translate-islamic-book
cd translate-islamic-book
./install.sh
```

`install.sh` creates the virtualenv, downloads the pinned datasets (about 140 MB, checked against
`data/MANIFEST.json`), links the skills, and finishes with `scripts.doctor`, which runs real lookups
and tells you whether the install is ready. Run it again if you move the folder.

Then ask Claude Code for what you want: "translate this book", "translate this lecture", "translate
this post". The matching skill picks it up. In this folder the skills load by themselves; `install.sh`
also makes them available everywhere.

For the DOCX, install the fonts where Word can see them: `cp assets/fonts/*.ttf ~/Library/Fonts/`.

## Why this exists

Machine translation of religious texts has an integrity problem: an LLM asked to "translate this
verse" will happily produce a fluent paraphrase that is *not* the received wording. This project
splits every span of the source into three lanes:

| Lane | Handling |
|---|---|
| **Qur'an** | Looked up in a verse dataset; the exact Arabic and an established English translation are pasted in. Never generated. |
| **Hadith** | Looked up by matn with orthography-folded matching; exact wording pasted in. |
| **The author's words** | Translated by the model, faithfully and consistently. |

## What "verified" means here

`out.verify` re-reads every quotation after assembly and compares it with the datasets, word by word:

| Status | Arabic | English | In the output |
|---|---|---|---|
| **Qur'an** | dataset | dataset | Anything else stops the book |
| **Verified hadith** | dataset | dataset | Plain |
| **Arabic only** | dataset | this edition's own rendering | Marked † |
| **Unverified** | as the author printed it | this edition's own rendering | Marked † |

The † is computed from that comparison, not taken from the translator's word, and the copyright page
states how many there are. A hadith lands in the last two rows when a collection has no English in
the datasets (Musnad Ahmad, Sunan al-Darimi), when the author quotes a variant the published English
doesn't cover, or when a collection isn't available at all (al-Hakim, al-Bayhaqi and others).

Two companion rules keep this honest. **Citations follow the author, wording follows the dataset:**
if the author printed a different number, the reader sees the author's. And **a run isn't finished
until `python -m scripts.gate runs/<slug>` exits 0**, for every format and every agent.

This verifies fidelity to the datasets. It does not grade hadith, and it does not replace review by a
qualified person: every book says so on its copyright page.

## How it works

```
BOOK    PDF ─▶ ingest ─▶ read ToC ─▶ chunk ─▶ translate ─▶ revise ─▶ assemble ─▶ verify + lint
                                                                         ─▶ PDF + DOCX + HTML
LECTURE URL/SRT ─▶ word timeline ─▶ blocks ─▶ translate ─▶ revise ─▶ retime ─▶ lint ─▶ .en.srt
POST    text/image ─▶ translate ─▶ check ─▶ plain text or thread

Every translator  ─▶ retrieval (quran_lookup, hadith_lookup) + the shared glossary
Every run         ─▶ scripts.gate
```

The step-by-step workflows live in [`skills/`](skills/):
[book](skills/translate-islamic-book/SKILL.md),
[lecture](skills/translate-srt/SKILL.md),
[post](skills/translate-post/SKILL.md).

Lecture timing is pure Python: the model never reads or writes a timestamp. Cues are re-segmented
into sentences and held to ≤42 characters × 2 lines and ≤20 characters per second.

The **master glossary** (`data/glossary.json`) is shared by every format. Lectures and posts add new
terms as they find them; a changed rendering of an existing term waits for your sign-off. A term whose
meaning depends on the discipline carries `senses`, so `الاعتبار` can be corroboration in hadith
science and taking a lesson elsewhere.

Work by Sheikh Ahmad bin Yusuf Al-Sayyid follows the higher-priority
[author translation profile](docs/translation-manuals/sheikh-ahmad-al-sayyid.md); its overrides are
run-local and do not silently change the shared glossary.

## Books

Each book comes out as a self-contained HTML file, an A5 PDF and an editable DOCX: typographic cover
and copyright page, table of contents, chapter openings with drop capitals, Qur'an set centered in a
mushaf face and hadith as distinct quotations, a glossary of the terms the book uses, indexes of every
verse and hadith cited, and the author's endnotes. Cardo for English, Amiri and Amiri Quran for
Arabic, black ink and one rubric red. The HTML and PDF are the verified deliverables; the DOCX is
checked structurally. Multi-paragraph source notes retain their scripture blocks inside the note,
including Arabic/English styles, ayah numbering, and any unverified-English marks.

## Repository layout

```
skills/        one SKILL.md per format
templates/     the translator and reviser briefs, the DOCX reference template
retrieval/     Qur'an + hadith lookup, glossary, verbatim comparison, index cache
ingest/  out/  book pipeline: chunking, assembly, verification, lint, conversion
subs/          lecture pipeline: timeline, segmentation, retiming, lint, scripture checks
scripts/       every CLI: gate, doctor, run_status, post, glossary, finish_*, ingest_*
data/          curated source (glossary, series notes, MANIFEST); datasets download here
editor/        local mobile-first SRT proofing app (`cd editor && python3 -m http.server 8777`)
assets/        embedded OFL fonts
tests/         pytest suite
AGENTS.md      the rulebook for any agent working here
```

```bash
.venv/bin/python -m pytest -q                      # everything
.venv/bin/python -m pytest -q -m "not integration" # without the datasets
```

## Data sources and credits

This tool *uses* third-party reference data and fonts. It does not redistribute them: datasets are
downloaded at setup, never committed.

- **Qur'an and hadith text and translations** come from
  [`fawazahmed0/quran-api`](https://github.com/fawazahmed0/quran-api) and
  [`hadith-api`](https://github.com/fawazahmed0/hadith-api) (API code under The Unlicense), **pinned to
  exact commits** and checked against a SHA-256 manifest, so the corpus a book was verified against
  can't drift silently. English Qur'an renderings include **Saheeh International** and **The Clear
  Quran**; hadith are given in their published English translations.
- **Musnad Ahmad and Sunan al-Darimi (Arabic)** come from
  [Open Hadith Data](https://github.com/mhashim6/Open-Hadith-Data), under the Open Database License,
  pinned the same way.
- **Fonts:** [Cardo](https://scholarsfonts.net/cardofnt.html),
  [Amiri](https://github.com/alif-type/amiri) and Amiri Quran, all under the SIL Open Font License.
- **Tooling:** [pandoc](https://pandoc.org), [poppler](https://poppler.freedesktop.org) and
  [yt-dlp](https://github.com/yt-dlp/yt-dlp).

> ⚠️ **Please note:** the Qur'an and hadith **English translations** retrieved by this tool are the
> copyrighted work of their publishers. This repository contains no scripture text or translations,
> only code that fetches and typesets them. You are responsible for complying with the licensing terms
> of any translation you use, and for respecting the copyright of any book or lecture you translate.

## License

The code is under the [MIT License](LICENSE). That covers **only the code**: not the datasets,
translations, fonts (SIL OFL, see [`assets/fonts/`](assets/fonts/)), or any material processed with
this tool, which keep their own licenses as noted above.
