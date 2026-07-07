# Book Design Overhaul + Cover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development for the LOGIC tasks (2, 3, 5) and superpowers:impeccable for the DESIGN tasks (4, cover in 4). Steps use checkbox (`- [ ]`) syntax.

**Goal:** Turn the current clean-but-monotone book into one with chapter openings that read as events, real print navigation (page numbers + running heads), a typographic cover, front/back matter, and Qur'an/Hadith citation indexes — same committed brand (PRODUCT.md), executed more confidently.

**Architecture:** Logic lives in `out/assemble.py` (front/back-matter blocks + index generation from markers, driven by a `book` metadata block). Presentation lives in `out/convert.py` (`_HTML_CSS` overhaul, cover + front-matter templates, `@page` rules) and `templates/reference.docx` (Word headers/ToC via `scripts/build_reference_docx.py`). Spec: `docs/superpowers/specs/2026-07-07-book-design-cover-design.md`.

**Tech Stack:** Python 3 stdlib + pytest; pandoc (fenced divs, raw HTML); Chrome headless for the visual gate (`/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`).

## Global Constraints

- Stdlib only in Python; self-contained HTML (fonts already embedded as data URIs: Cardo, Amiri, Amiri Quran — all OFL).
- Brand is fixed by PRODUCT.md: reverent, Islamic Texts Society class, ink + ONE vermilion rubric (`--rubric` oklch(0.44 0.14 29)); NO cards/panels/sidebars/UI fonts; sacred text distinguished by setting not boxes; every Arabic glyph screenshot-verified.
- Body ≥ 4.5:1 contrast; semantic heading hierarchy (h1 title → h2 chapter → h3 segment → h4 benefits); print readable in monochrome.
- Markers to parse (already in every assembled `book.md`): `<!--quran s=<surah> a=<a0>-<a1> tr=...-->` and `<!--hadith coll=<collection> num=<number> conf=<c> src=<dataset|fallback>-->`.
- Index entries reference CHAPTER (nearest preceding `## ` heading), NOT page numbers (HTML/DOCX/print reflow; browsers can't cross-reference page numbers without a pagination framework — accepted limitation). HTML index entries hyperlink to the citation.
- Retrofit is build-only (re-assemble+convert the 3 books); translated chunks are never re-run.
- Commit directly to `main`. NEVER `git push`. Do NOT `git push --force`/`reset --hard`.
- The cover DIRECTION is chosen from rendered mockups at build time. Since this run is autonomous, the builder produces 2–3 mockups, picks the strongest with written rationale, and surfaces all options in the final report for the user to redirect.

---

### Task 1: `@page` margin-box probe (RISK GATE — do first)

**Files:** Create (temporary, not committed): `/tmp/page-probe.html`

**Why:** The navigation design depends on whether the user's Chrome honors CSS `@page` margin boxes (`@top-center`, `@bottom-center` with `counter(page)` and running `string-set`). If it doesn't, running heads are dropped and only page numbers (widely supported) remain. Decide before building Task 4's navigation CSS.

- [ ] **Step 1: Write the probe**

Create `/tmp/page-probe.html` with two mechanisms to test:
```html
<style>
  @page { size: A5; margin: 18mm;
    @bottom-center { content: counter(page); }
    @top-center { content: string(chaptitle); font-style: italic; } }
  h2 { string-set: chaptitle content(text); page-break-before: always; }
  .filler { height: 260mm; }
</style>
<h2>First Chapter</h2><p>Body.</p><div class="filler"></div>
<h2>Second Chapter</h2><p>Body two.</p><div class="filler"></div>
```

- [ ] **Step 2: Render to PDF headless and inspect**

Run:
```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless \
  --print-to-pdf=/tmp/page-probe.pdf --no-pdf-header-footer /tmp/page-probe.html
pdftotext -layout /tmp/page-probe.pdf - | head -40
```
Look for: a page number at the bottom of each page, and the chapter title at the top of pages after the first. Also render a screenshot of page 2 (`pdftoppm -png -f 2 -l 2 /tmp/page-probe.pdf /tmp/page-probe`).

- [ ] **Step 3: Record the decision**

Write the finding to the report: does `counter(page)` work? does `string(chaptitle)` running-head work? This gates Task 4's navigation section:
- both work → full page numbers + running heads.
- only `counter(page)` → page numbers only, no running heads (still a real improvement).
- neither → skip print navigation, keep the existing `@page{margin}` only, note it.

---

### Task 2: Citation indexes in `out/assemble.py`

**Files:**
- Modify: `out/assemble.py` (add `build_indexes`, wire into `assemble`)
- Test: `tests/test_assemble.py` (append index tests)

**Interfaces:**
- Consumes: the assembled book markdown (with markers intact — indexes are built BEFORE marker text is transformed by convert; assemble keeps markers).
- Produces: `build_indexes(book_md: str) -> str` returning markdown for two sections: `## Index of Qur'anic Verses` (entries `Surah N:A0–A1 … <chapter title>`, sorted by (surah, a0)) and `## Index of Hadith` (entries `<Collection> <number> … <chapter title>`, sorted by collection then number). Each entry links in HTML via a pandoc anchor. Returns `""` if there are no markers of that kind. `assemble(..., indexes=False)` appends them (after the glossary appendix, before any colophon) when enabled; `--indexes` CLI flag.

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_assemble.py
from out.assemble import build_indexes

_IDX_MD = """## Chapter One

<!--quran s=2 a=255-255 tr=saheeh-->
آية [X]
"t" [X]
<!--/quran-->

<!--hadith coll=bukhari num=1 conf=1.0 src=dataset-->
«متن»
"t" (al-Bukhari 1)
<!--/hadith-->

## Chapter Two

<!--quran s=1 a=1-3 tr=saheeh-->
آية [X]
"t" [X]
<!--/quran-->
"""


def test_build_indexes_has_both_sections_sorted():
    out = build_indexes(_IDX_MD)
    assert "## Index of Qur'anic Verses" in out
    assert "## Index of Hadith" in out
    # surah 1 sorts before surah 2
    assert out.index("Surah 1:1") < out.index("Surah 2:255")


def test_index_entry_names_its_chapter():
    out = build_indexes(_IDX_MD)
    # the 2:255 verse lives under Chapter One; 1:1-3 under Chapter Two
    assert "Chapter One" in out and "Chapter Two" in out


def test_hadith_index_lists_collection_and_number():
    out = build_indexes(_IDX_MD)
    assert "al-Bukhari 1" in out or "Bukhari 1" in out


def test_build_indexes_empty_when_no_markers():
    assert build_indexes("## Chapter\n\nplain prose, no citations.") == ""


def test_single_ayah_renders_without_range_dash():
    out = build_indexes(_IDX_MD)
    assert "Surah 2:255" in out and "255–255" not in out
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_assemble.py -k index -v`
Expected: FAIL — `ImportError: cannot import name 'build_indexes'`

- [ ] **Step 3: Implement**

```python
# add to out/assemble.py
_H2 = re.compile(r"^##\s+(?!Index of|Glossary)(.+?)\s*$", re.M)
_QURAN_MARK = re.compile(r"<!--quran\s+s=(\d+)\s+a=(\d+)-(\d+)[^>]*-->")
_HADITH_MARK = re.compile(r"<!--hadith\s+coll=(\w+)\s+num=(\S+)[^>]*-->")

_COLL_NAMES = {
    "bukhari": "al-Bukhari", "muslim": "Muslim", "abudawud": "Abu Dawud",
    "tirmidhi": "al-Tirmidhi", "nasai": "al-Nasa'i", "ibnmajah": "Ibn Majah",
    "malik": "Malik", "ahmad": "Ahmad", "darimi": "al-Darimi",
    "hakim": "al-Hakim", "bayhaqi": "al-Bayhaqi",
}


def _chapter_at(md, pos):
    """The nearest '## ' chapter heading at or before pos (else 'Front matter')."""
    best = "Front matter"
    for m in _H2.finditer(md):
        if m.start() <= pos:
            best = m.group(1)
        else:
            break
    return best


def build_indexes(book_md):
    verses, hadith = [], []
    for m in _QURAN_MARK.finditer(book_md):
        s, a0, a1 = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if s == 0:
            continue  # fallback marker, not a locatable citation
        verses.append((s, a0, a1, _chapter_at(book_md, m.start())))
    for m in _HADITH_MARK.finditer(book_md):
        coll, num = m.group(1), m.group(2)
        hadith.append((coll, num, _chapter_at(book_md, m.start())))
    if not verses and not hadith:
        return ""
    out = []
    if verses:
        out.append("## Index of Qur'anic Verses\n")
        seen = set()
        for s, a0, a1, chap in sorted(verses, key=lambda v: (v[0], v[1], v[2])):
            ref = "Surah %d:%d" % (s, a0) + ("" if a0 == a1 else "–%d" % a1)
            key = (ref, chap)
            if key in seen:
                continue
            seen.add(key)
            out.append("%s — *%s*  " % (ref, chap))
        out.append("")
    if hadith:
        out.append("## Index of Hadith\n")
        seen = set()
        def _sortkey(h):
            try:
                return (h[0], int(h[1]))
            except ValueError:
                return (h[0], 1 << 30)
        for coll, num, chap in sorted(hadith, key=_sortkey):
            ref = "%s %s" % (_COLL_NAMES.get(coll, coll.title()), num)
            key = (ref, chap)
            if key in seen:
                continue
            seen.add(key)
            out.append("%s — *%s*  " % (ref, chap))
        out.append("")
    return "\n".join(out)
```

Wire into `assemble()` (after the glossary append, before writing) behind an `indexes=False` param, and add a `--indexes` CLI flag.

- [ ] **Step 4: Run to verify pass**

Run: `.venv/bin/python -m pytest tests/test_assemble.py -k index -v`
Expected: 5 passed

- [ ] **Step 5: Real-book smoke** — build bawsala's indexes and eyeball counts:

```bash
.venv/bin/python -c "from out.assemble import build_indexes; import io; md=open('runs/bawsala/work/book.md',encoding='utf-8').read(); print(build_indexes(md)[:800])"
```
Expected: an Index of Qur'anic Verses and Index of Hadith with real surah refs + chapter names.

- [ ] **Step 6: Full suite + commit**

Run: `.venv/bin/python -m pytest -m "not integration"`
```bash
git add out/assemble.py tests/test_assemble.py
git commit -m "feat(assemble): Qur'an + Hadith citation indexes (--indexes)"
```

---

### Task 3: Front & back matter in `out/assemble.py`

**Files:**
- Modify: `out/assemble.py` (add `front_matter`, `back_matter`; extend the `book`-metadata plumbing)
- Test: `tests/test_assemble.py`

**Interfaces:**
- Consumes: a `meta` dict (from the book's `work/glossary.json` `book` block + assemble args): `{title_en, title_ar, author_en, author_ar, subtitle_en?, edition?, year?, translator?}`.
- Produces: `front_matter(meta) -> str` (a `::: {.cover}` block + `::: {.half-title}` + `::: {.copyright}` fenced divs as raw markdown; the pandoc title block/ToC still follow) and `back_matter() -> str` (a `::: {.colophon}` block). Wired so the final assembled order is: cover → half-title → title block (existing) → copyright → ToC (existing, from convert) → body → glossary → indexes → colophon. Enabled by `matter=False` param + `--matter` flag. `translator`/`edition`/`year` are optional; omit their lines when absent.

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_assemble.py
from out.assemble import front_matter, back_matter

_META = {"title_en": "The Reformer's Compass", "title_ar": "بوصلة المصلح",
         "author_en": "Ahmad ibn Yusuf al-Sayyid", "author_ar": "أحمد بن يوسف السيد",
         "translator": "Mo", "edition": "First Edition", "year": "2026"}


def test_front_matter_has_cover_and_copyright_with_arabic_title():
    fm = front_matter(_META)
    assert "{.cover}" in fm and "{.copyright}" in fm
    assert "بوصلة المصلح" in fm and "The Reformer's Compass" in fm
    assert "lang=ar" in fm  # Arabic title carries lang/dir


def test_front_matter_translator_and_sacred_note_present():
    fm = front_matter(_META)
    assert "Mo" in fm
    # sacred-text sourcing note (Saheeh International + verified)
    assert "Saheeh International" in fm and "verified" in fm.lower()


def test_front_matter_omits_absent_optional_lines():
    fm = front_matter({"title_en": "X", "title_ar": "س", "author_en": "A", "author_ar": "ع"})
    assert "Edition" not in fm and "Translated by" not in fm


def test_back_matter_is_colophon():
    assert "{.colophon}" in back_matter()
```

- [ ] **Step 2: Run to verify fail**

Run: `.venv/bin/python -m pytest tests/test_assemble.py -k "front_matter or back_matter" -v`
Expected: FAIL — ImportError.

- [ ] **Step 3: Implement**

```python
# add to out/assemble.py
def _ar(s):
    return "[%s]{lang=ar dir=rtl}" % s


def front_matter(meta):
    cover = ('::: {.cover}\n'
             '%s\n\n# %s\n\n%s\n\n%s\n:::\n\n'
             % (_ar(meta["title_ar"]), meta["title_en"],
                _ar(meta["author_ar"]), meta["author_en"]))
    half = '::: {.half-title}\n%s\n:::\n\n' % meta["title_en"]
    lines = ["::: {.copyright}", "**%s**  " % meta["title_en"],
             "%s  " % meta["author_en"]]
    if meta.get("translator"):
        lines.append("Translated by %s  " % meta["translator"])
    if meta.get("edition"):
        lines.append("%s  " % meta["edition"])
    if meta.get("year"):
        lines.append("%s  " % meta["year"])
    lines += ["",
              "Qur'anic quotations are the Saheeh International translation; "
              "hadith are given in their published translations. All sacred "
              "text is retrieved verbatim from source datasets and "
              "machine-verified, never machine-written.", ":::", ""]
    return cover + half + "\n".join(lines) + "\n"


def back_matter():
    return ("\n\n::: {.colophon}\n"
            "Set in Cardo and Amiri. Composed with the translate-islamic-book "
            "pipeline.\n:::\n")
```

Wire into `assemble()`: prepend `front_matter(meta)` BEFORE the pandoc title block, append `back_matter()` at the very end, behind `matter=False` + `--matter`. `meta` is loaded from the glossary's `book` block when `--glossary` is given, overlaid with `--edition/--year/--translator` args if present.

**Front-matter ORDER note (resolved in Task 4):** the spec order is cover → half-title → title page → copyright → ToC, but pandoc auto-generates its `% title` block at the very top. Task 4 owns the decision of whether to keep pandoc's title block (accepting cover→half-title→copyright→title→ToC) or render the title page as a `.title-page` div here too and drop `--title` from the pandoc call (giving the exact spec order). Decide against live renders; if the latter, move the copyright div after the title-page div in `front_matter` and restyle `header#title-block-header` → `.title-page`.

- [ ] **Step 4: Pass + full suite + commit**

Run: `.venv/bin/python -m pytest tests/test_assemble.py -k "front_matter or back_matter" -v` → 4 passed
Run: `.venv/bin/python -m pytest -m "not integration"`
```bash
git add out/assemble.py tests/test_assemble.py
git commit -m "feat(assemble): front/back matter (cover, half-title, copyright, colophon)"
```

---

### Task 4: Interior + front-matter + cover CSS in `out/convert.py` (DESIGN — impeccable session)

**This task is executed by the controller using superpowers:impeccable with live Chrome rendering, not transcribed from pre-written code.** The plan fixes the REQUIREMENTS and the verification bar; the exact CSS is designed against real renders.

**Files:** Modify `out/convert.py` (`_HTML_CSS`, and add cover/front-matter/colophon/index/`@page` rules). Verified by screenshot, no unit test.

**Design requirements (each verified in a Chrome screenshot at A5 print emulation + desktop + mobile):**

- [ ] **Cover** (`.cover`): full-bleed first page; Arabic title set large in Amiri (display size), English title below, author, quiet imprint feel. Produce 2–3 directions (e.g. centered-classical / rule-framed / asymmetric-modern-classical), screenshot each, pick the strongest with written rationale, keep it strictly typographic (PRODUCT.md anti-references stand). `page-break-after: always`.
- [ ] **Half-title / copyright / colophon**: quiet, centered, small; copyright page left-aligned block at the foot; colophon centered italic. Each on its own page in print.
- [ ] **Chapter openings as events** (`h2`): more presence than today's centered rubric line — chapter treatment with generous drop into the text; keep the ONE vermilion; no boxes. `page-break-before: always`.
- [ ] **Reading comfort**: audit measure (~34em is current), leading, size; verify verse/hadith Arabic–English balance still holds after the h2 change.
- [ ] **Navigation** (per Task 1 result): `@page` page numbers, and running heads (book title verso / chapter recto via `string-set`) IF the probe passed; else page numbers only. Suppress folios on cover/half-title.
- [ ] **Index styling** (`## Index of…` inherit h2; entries): compact, ragged-right, chapter name in italic, dot leader optional; hyperlinks inherit ink.
- [ ] **Monochrome check**: the whole thing legible with color off (print).

- [ ] **Commit** once all screenshots pass:
```bash
git add out/convert.py
git commit -m "feat(convert): cover, front/back matter, chapter openings, print navigation, index styling"
```

---

### Task 5: DOCX headers/ToC via `templates/reference.docx`

**Files:** Modify `scripts/build_reference_docx.py` (regenerate `templates/reference.docx`).

**Interfaces:** the reference.docx pandoc uses (`--reference-doc`) gains page-numbered footers and confirms the Word ToC field. New paragraph styles are only needed if convert maps front-matter divs to `custom-style`s; otherwise the fenced divs render as plain paragraphs in DOCX (acceptable — HTML is the visually-verified deliverable).

- [ ] **Step 1** Inspect the current `scripts/build_reference_docx.py` and add a page-number footer to the default section (python-docx or the documented approach the script already uses). Keep existing Quran/Hadith paragraph styles intact.
- [ ] **Step 2** Regenerate: `python scripts/build_reference_docx.py`; confirm `templates/reference.docx` rebuilt.
- [ ] **Step 3** Build a book to DOCX and confirm pandoc still succeeds with the new reference doc (structural check only — no local Word to render).
- [ ] **Step 4** Commit `scripts/build_reference_docx.py` + `templates/reference.docx`.

---

### Task 6: Rebuild the 3 books + visual verification (retrofit)

**Files:** regenerate each `runs/<book>/output/book.{html,docx}` (gitignored — no commit).

- [ ] **Step 1** For each of anwar / alminhaj / bawsala, re-run assemble with `--glossary <book>/work/glossary.json --indexes --matter` (+ the book's original `--title/--author/--no-hadith-numbers` and now `--translator/--edition/--year` if known) then `out.convert`.
- [ ] **Step 2** Screenshot each book's: cover, a chapter opening, a Qur'an verse block (confirm still mushaf — regression guard from Plan B), the glossary, and an index page. Controller inspects all.
- [ ] **Step 3** Report the regenerated `output/book.html` paths + the cover direction chosen, for the user's sign-off. No commit.
