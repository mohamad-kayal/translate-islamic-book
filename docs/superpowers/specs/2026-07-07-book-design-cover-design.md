# Book design overhaul + cover — design

Date: 2026-07-07 · Status: approved in brainstorm (all four interior pains + in-book cover page + citation index)

## Problem

The current output has real bones (Cardo/Amiri, justified hyphenated prose, centered verse
settings, spaced title page) but the user finds it lacking on all four axes asked: pages read
monotone (chapter openings aren't events, the vermilion is shy), navigation is weak (no running
heads or page numbers in print, plain ToC), body reading comfort can improve, and front/back
matter is thin (title page then straight into text). There is also no cover. Goal: the same
committed brand — reverent, Islamic Texts Society class, ink + one vermilion (PRODUCT.md) —
executed more confidently, not replaced.

## Decisions (locked)

1. **Full interior pass** across all four pains (rhythm, navigation, comfort, front/back matter).
2. **Cover = a page in the book**: full-bleed typographic first page in HTML/print and DOCX. No
   print-on-demand wraparound (spine/back/bleed) this round.
3. **Cover direction chosen visually at build time** from 2–3 rendered mockups presented to the
   user. Strictly typographic/calligraphic; PRODUCT.md anti-references stand.
4. **Citation index ships in this workstream** (it is the scholarly half of navigation).
5. Retrofit is free: everything lives in assemble/convert, so existing books get the upgrade by
   re-running those two steps (same path as the glossary-appendix retrofit).

## Workpieces

### Interior rhythm (the monotony fix)

Chapter openings as events: chapter number treatment + rubricated title + generous drop into the
text; section dividers with breathing room; more confident use of the one vermilion. Rhythm, not
decoration — no ornaments-for-ornament's-sake, nothing boxed.

### Navigation

- Print: page numbers + running heads (book title verso / chapter title recto) via CSS `@page`
  margin boxes — native in modern Chromium print-to-PDF; NO pagination framework.
- DOCX: real headers/footers with page numbers + a Word ToC field, via a new pandoc
  `assets/reference.docx`.
- HTML ToC stays hyperlinks (screen); refined visual treatment.

### Reading comfort

Audit measure / leading / size, verse-block Arabic–English balance, footnote and list styling,
hyphenation quality. Judged on rendered screenshots, not in the abstract.

### Front & back matter

Order: cover → half-title → title page → copyright/edition page → ToC → text → glossary appendix
(other spec) → citation indexes → colophon. The copyright/edition page carries the translator credit and a sacred-text
sourcing note (Quran English = Saheeh International; hadith English = collection translations;
all machine-verified verbatim against the datasets).

### Cover page

Full-bleed typographic first page: Arabic title set large (Amiri display, or another OFL Arabic
display face only if it clearly earns its place — self-contained/embedded either way), English
title + author, quiet imprint feel. 2–3 mockup directions → user picks → refine.

### Citation index

`out.assemble` generates "Index of Qur'anic Verses" (surah:ayah order) and "Index of Hadith"
(collection + number) from the markers it already parses. Entries reference chapter/section —
stable across HTML/DOCX/print and honest in reflowable formats — and hyperlink in HTML. No page
numbers in index entries (see risks).

## Mechanics

- `out/convert.py`: CSS overhaul, cover + front-matter templates, `@page` rules, index/appendix
  styling.
- `out/assemble.py`: front-matter blocks, index generation.
- `assets/reference.docx`: Word headers/footers/ToC (committed binary asset).
- Book metadata (edition, year, translator line, imprint) extends the `book` block of
  `work/glossary.json` — the file assemble already receives under the glossary spec. One metadata
  source; no new flags beyond `--glossary`.

## Method (build session)

UI work → the impeccable skill runs the session: commit to direction before CSS; screenshot-gate
every claim (print emulation + desktop + mobile widths); Arabic shaping verified glyph-by-glyph;
monochrome print check (PRODUCT.md accessibility). Test targets: Al-Minhaj (hardest: 37 chapters,
237 hadith) and Anwar. Bawsala gains the treatment at its assemble step.

## Risks (verify FIRST in the build session)

- `@page` margin-box support in the user's installed Chrome: verify with a probe page before
  building on it. Fallback: page numbers only (widely supported), drop running heads.
- ToC/index page numbers in HTML print: browsers cannot cross-reference page numbers without a
  pagination framework — accepted limitation this round (DOCX/Word does it natively). Revisit
  paged.js only if this hurts in practice.
- New display font (if any): OFL license, embedded, shaping screenshot-verified like the others.

## Testing

- pytest: assemble front-matter blocks + index generation from fixture markers (order, refs,
  anchors); metadata plumb-through from the `book` block.
- Rendered: screenshot suite per Method; before/after spreads for the user's sign-off.
- Regression: existing verify suite still passes on re-assembled books (markers untouched).

## Out of scope (deliberate)

- Print-on-demand wraparound cover (spine width, back blurb, bleed).
- EPUB output; paged.js; image/photographic covers; names index.
