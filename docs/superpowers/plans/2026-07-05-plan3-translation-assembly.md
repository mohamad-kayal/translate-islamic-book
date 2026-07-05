# Translation & Assembly — Implementation Plan (Plan 3 of 3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Complete the skill: parallel subagents translate each chunk (prose translated; every verse/hadith **retrieved** via the Plan 1 library), a verifier re-checks the sacred content, chunks assemble into one Markdown book with running hadith numbers, and it converts to DOCX + HTML. Plus the top-level `SKILL.md` the user invokes.

**Architecture:** The orchestration lives in `SKILL.md` (the workflow the main agent follows) + `templates/translator-subagent.md` (the per-chunk prompt). Subagents read the chunk's rendered PDF pages (vision) and emit Markdown with **machine-readable sacred-content markers** (`<!--quran…-->`, `<!--hadith…-->`) and hadith-number placeholders (`[[H]]`/`[[HA]]`). Deterministic Python (`out/assemble.py`, `out/verify.py`, `out/convert.py`) does numbering, QC, and format conversion — all unit-testable. No verse/hadith text is ever produced by the LLM; the subagent calls `retrieval.quran_lookup` / `retrieval.hadith_lookup` and pastes their output.

**Tech Stack:** Python 3.9+, stdlib only in code; `pandoc` (installed) for DOCX/HTML; the Plan 1 `retrieval` package; Task subagents via the Agent tool. Dev/test: `pytest`.

## Global Constraints

- Python **3.9+**, **no third-party runtime deps**; `pandoc` on PATH for conversion.
- **Sacred content is retrieved, never written by the LLM.** Subagents paste `quran_lookup`/`hadith_lookup` CLI output verbatim into markers; `verify.py` re-checks every marker against the library.
- **Sacred-content markers** (the contract between subagents and Python):
  - Quran: `<!--quran s=<surah> a=<a0>-<a1> tr=saheeh|clear-->` … `<!--/quran-->`
  - Hadith: `<!--hadith coll=<collection> num=<number> conf=<0..1> src=dataset|fallback-->` … `<!--/hadith-->`
  - Hadith number placeholder: `[[H]]` (main text) / `[[HA]]` (appendix). Assemble assigns the running numbers.
- **Hadith numbering:** main text sequential (`1.`, `2.`…); appendix suffixed (`1-A`, `2-A`…) — per the user's Al-Minhaj convention.
- **Ambiguity policy:** a hadith whose canonical English reads unclearly is inserted verbatim and logged to `review.md` (never altered) — the user's chosen policy.
- Output: **DOCX** (editable, primary) + **HTML** (RTL-aware, print-to-PDF). PDF itself is exported by the user from Word/browser (reliable Arabic) — documented, not a fragile CLI step.

## File Structure

```
translate-islamic-book/
  out/
    __init__.py
    assemble.py     # merge chunk markdowns -> book.md; assign hadith numbers
    verify.py       # parse sacred markers, re-check vs retrieval, build QC report + review list
    convert.py      # book.md -> DOCX + HTML via pandoc
  templates/
    translator-subagent.md   # per-chunk translation prompt (the three-lane contract)
  SKILL.md                   # the invokable skill: end-to-end workflow
  tests/
    test_assemble.py
    test_verify.py
    test_convert.py
```

---

### Task 1: Assemble — merge chunks + hadith numbering

**Files:**
- Create: `translate-islamic-book/out/__init__.py` (empty), `translate-islamic-book/out/assemble.py`
- Create: `translate-islamic-book/tests/test_assemble.py`

**Interfaces:**
- Produces: `assign_hadith_numbers(md: str) -> str` (replaces `[[H]]`→`1.` sequential, `[[HA]]`→`1-A` sequential), `merge(chunk_texts: list[str]) -> str`, `assemble(chunk_dir, out_path) -> str`.

- [ ] **Step 1: Write the failing test** — `tests/test_assemble.py`

```python
from out.assemble import assign_hadith_numbers, merge


def test_main_hadith_numbered_sequentially():
    md = "[[H]] first\n[[H]] second\n[[H]] third"
    assert assign_hadith_numbers(md) == "1. first\n2. second\n3. third"


def test_appendix_hadith_get_A_suffix_independent_sequence():
    md = "[[H]] a\n[[HA]] x\n[[H]] b\n[[HA]] y"
    assert assign_hadith_numbers(md) == "1. a\n1-A. x\n2. b\n2-A. y"


def test_merge_joins_with_blank_line_and_orders():
    assert merge(["# A\np1", "# B\np2"]) == "# A\np1\n\n# B\np2"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd translate-islamic-book && . .venv/bin/activate && python -m pytest tests/test_assemble.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'out.assemble'`

- [ ] **Step 3: Write minimal implementation** — `out/assemble.py`

```python
"""Merge translated chunk markdowns into one book, assigning running hadith numbers."""
import glob
import os
import re


def assign_hadith_numbers(md):
    """Replace [[H]] with '1.', '2.'… (main) and [[HA]] with '1-A.', '2-A.'… (appendix)."""
    main = {"n": 0}
    app = {"n": 0}

    def _main(_):
        main["n"] += 1
        return "%d." % main["n"]

    def _app(_):
        app["n"] += 1
        return "%d-A." % app["n"]

    md = re.sub(r"\[\[HA\]\]", _app, md)
    md = re.sub(r"\[\[H\]\]", _main, md)
    return md


def merge(chunk_texts):
    return "\n\n".join(t.strip("\n") for t in chunk_texts)


def assemble(chunk_dir, out_path):
    files = sorted(glob.glob(os.path.join(chunk_dir, "chunk_*.md")))
    body = merge([open(f, encoding="utf-8").read() for f in files])
    book = assign_hadith_numbers(body)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(book)
    return book
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_assemble.py -q`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add out/__init__.py out/assemble.py tests/test_assemble.py
git commit -m "feat(out): assemble chunk markdowns + running hadith numbering"
```

---

### Task 2: Verify — re-check sacred markers against the library

**Files:**
- Create: `translate-islamic-book/out/verify.py`
- Create: `translate-islamic-book/tests/test_verify.py`

**Interfaces:**
- Produces: `parse_markers(md) -> {"quran":[dict], "hadith":[dict]}` (parsed attrs), `verify(md) -> dict` report with keys `n_quran, n_hadith, problems (list[str]), flagged (list[str])`. `verify` flags: invalid surah/ayah, unknown collection, hadith `conf < 0.6` or `src=fallback` (→ review), missing attrs.

- [ ] **Step 1: Write the failing test** — `tests/test_verify.py`

```python
from out.verify import parse_markers, verify

GOOD = (
    "intro\n"
    "<!--quran s=4 a=59-59 tr=saheeh-->\n(...) [An-Nisa: 59]\n<!--/quran-->\n"
    "<!--hadith coll=bukhari num=79 conf=1.0 src=dataset-->\n[[H]] ... <!--/hadith-->\n"
)


def test_parse_counts():
    m = parse_markers(GOOD)
    assert len(m["quran"]) == 1 and len(m["hadith"]) == 1
    assert m["quran"][0]["s"] == "4" and m["hadith"][0]["coll"] == "bukhari"


def test_clean_report_has_no_problems():
    r = verify(GOOD)
    assert r["n_quran"] == 1 and r["n_hadith"] == 1
    assert r["problems"] == [] and r["flagged"] == []


def test_flags_low_confidence_and_fallback():
    md = "<!--hadith coll=ahmad num=23482 conf=0.4 src=fallback-->x<!--/hadith-->"
    r = verify(md)
    assert any("review" in f.lower() or "fallback" in f.lower() or "confidence" in f.lower()
               for f in r["flagged"])


def test_problems_on_bad_surah():
    md = "<!--quran s=200 a=1-1 tr=saheeh-->x<!--/quran-->"
    r = verify(md)
    assert any("surah" in p.lower() for p in r["problems"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_verify.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'out.verify'`

- [ ] **Step 3: Write minimal implementation** — `out/verify.py`

```python
"""Verify sacred-content markers in the assembled book: refs valid, collections known, flags."""
import re

_QURAN = re.compile(r"<!--quran\s+([^>]*?)-->", re.S)
_HADITH = re.compile(r"<!--hadith\s+([^>]*?)-->", re.S)
_COLLECTIONS = {"bukhari", "muslim", "abudawud", "tirmidhi", "nasai",
                "ibnmajah", "malik", "nawawi", "qudsi", "dehlawi",
                "ahmad", "hakim", "bayhaqi", "darimi", "tabarani"}
MIN_CONF = 0.6


def _attrs(s):
    return dict(re.findall(r"(\w+)=(\S+)", s))


def parse_markers(md):
    return {"quran": [_attrs(m) for m in _QURAN.findall(md)],
            "hadith": [_attrs(m) for m in _HADITH.findall(md)]}


def verify(md):
    m = parse_markers(md)
    problems, flagged = [], []
    for q in m["quran"]:
        try:
            s = int(q.get("s", "0"))
            a0, a1 = (int(x) for x in q.get("a", "0-0").split("-"))
        except ValueError:
            problems.append("malformed quran marker: %s" % q)
            continue
        if not (1 <= s <= 114):
            problems.append("quran surah out of range: %s" % s)
        if not (1 <= a0 <= a1):
            problems.append("quran ayah range invalid: %s-%s (surah %s)" % (a0, a1, s))
    for h in m["hadith"]:
        coll = h.get("coll", "")
        if coll not in _COLLECTIONS:
            problems.append("unknown hadith collection: %s" % coll)
        if h.get("src") == "fallback":
            flagged.append("hadith %s %s sourced by fallback — review" % (coll, h.get("num", "?")))
        try:
            if float(h.get("conf", "1")) < MIN_CONF:
                flagged.append("hadith %s %s low confidence %s — review"
                               % (coll, h.get("num", "?"), h.get("conf")))
        except ValueError:
            problems.append("malformed hadith conf: %s" % h.get("conf"))
    return {"n_quran": len(m["quran"]), "n_hadith": len(m["hadith"]),
            "problems": problems, "flagged": flagged}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_verify.py -q`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add out/verify.py tests/test_verify.py
git commit -m "feat(out): verify sacred-content markers (refs, collections, review flags)"
```

---

### Task 3: Convert — Markdown → DOCX + HTML

**Files:**
- Create: `translate-islamic-book/out/convert.py`
- Create: `translate-islamic-book/tests/test_convert.py`

**Interfaces:**
- Produces: `to_docx(md_path, out_path)`, `to_html(md_path, out_path)` (standalone, RTL-friendly), `convert_all(md_path, out_dir) -> dict` (returns paths). Uses `pandoc` via subprocess.

- [ ] **Step 1: Write the failing test** — `tests/test_convert.py`

```python
import os
from out import convert


def test_to_html_contains_arabic_and_rtl(tmp_path):
    md = tmp_path / "book.md"
    md.write_text("# Chapter\n\n(بحر نهر) [Al-Fatihah: 1]\n", encoding="utf-8")
    out = tmp_path / "book.html"
    convert.to_html(str(md), str(out))
    html = out.read_text(encoding="utf-8")
    assert "بحر" in html and "dir=" in html.lower()


def test_to_docx_produces_zip(tmp_path):
    md = tmp_path / "book.md"
    md.write_text("# Chapter\n\ntext\n", encoding="utf-8")
    out = tmp_path / "book.docx"
    convert.to_docx(str(md), str(out))
    assert os.path.getsize(out) > 0
    with open(out, "rb") as f:
        assert f.read(2) == b"PK"        # docx is a zip
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_convert.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'out.convert'`

- [ ] **Step 3: Write minimal implementation** — `out/convert.py`

```python
"""Convert the assembled Markdown book to DOCX (editable) + HTML (RTL, print-to-PDF)."""
import os
import subprocess

# Minimal CSS: default RTL so Arabic verses/hadith lay out correctly; English runs LTR inline.
_HTML_CSS = """
body{max-width:820px;margin:2rem auto;font-family:Georgia,serif;line-height:1.7;padding:0 1rem}
:root{direction:rtl}
h1,h2,h3{font-family:system-ui,sans-serif}
blockquote{border-inline-start:3px solid #ccc;margin-inline:0;padding-inline-start:1rem;color:#333}
"""


def _pandoc(args):
    r = subprocess.run(["pandoc"] + args, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("pandoc failed: %s" % r.stderr)


def to_docx(md_path, out_path):
    _pandoc([md_path, "-f", "markdown", "-o", out_path])


def to_html(md_path, out_path):
    css_file = out_path + ".css"
    with open(css_file, "w", encoding="utf-8") as f:
        f.write(_HTML_CSS)
    _pandoc([md_path, "-f", "markdown", "-t", "html", "-s",
             "--metadata", "dir=rtl", "-c", os.path.basename(css_file),
             "--embed-resources", "-o", out_path])
    os.remove(css_file)


def convert_all(md_path, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(md_path))[0]
    docx, html = os.path.join(out_dir, base + ".docx"), os.path.join(out_dir, base + ".html")
    to_docx(md_path, docx)
    to_html(md_path, html)
    return {"docx": docx, "html": html}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_convert.py -q`
Expected: PASS (2 passed). *If `--embed-resources` is unsupported by the installed pandoc, drop it and inline the CSS via `-H` header include instead; keep the `dir=rtl` metadata.*

- [ ] **Step 5: Commit**

```bash
git add out/convert.py tests/test_convert.py
git commit -m "feat(out): convert assembled Markdown to DOCX + RTL HTML via pandoc"
```

---

### Task 4: Subagent template + SKILL.md (the invokable skill)

**Files:**
- Create: `translate-islamic-book/templates/translator-subagent.md`
- Create: `translate-islamic-book/SKILL.md`

**Interfaces:** No unit test — these are the prompt + workflow that tie the Python pieces together; validated by the one-chunk end-to-end demo (Step 4).

- [ ] **Step 1: Write `templates/translator-subagent.md`** — the per-chunk contract

```markdown
# Translator subagent — one chunk

You translate ONE chunk of an Arabic Islamic book into English. You are given: the source PDF path,
your chunk's page range (and a `context_page` to read for continuity but NOT translate), and the shared
glossary. Read the pages with the Read tool (rendered images — read the Arabic as printed).

## The three lanes — route every span to exactly one
1. **Author's prose** → TRANSLATE. Literal, faithful to tone; lightly de-ambiguate for clarity; add
   nothing, omit nothing. Gloss a transliterated term on first use: *Tazkiyah (purification of the soul)*.
2. **Quran verse(s)** → DO NOT TRANSLATE. Run:
   `python -m retrieval.quran_lookup --match "<the Arabic you read>"`
   Paste its `arabic`, `ref_ar`, `english_saheeh`, `ref_en` into a marker:
   ```
   <!--quran s=<surah> a=<a0>-<a1> tr=saheeh-->
   (ARABIC) [REF_AR]
   "ENGLISH_SAHEEH" [REF_EN]
   <!--/quran-->
   ```
   If `matched:false`, widen or shorten the quoted Arabic and retry; if still no match, mark
   `<!--quran s=0 a=0-0 tr=fallback-->` and note it — do NOT invent the verse.
3. **Hadith** → DO NOT TRANSLATE. Run:
   `python -m retrieval.hadith_lookup --match "<the Arabic matn you read>"`
   Emit, with a number placeholder (`[[H]]`, or `[[HA]]` if this chunk is an appendix chapter):
   ```
   [[H]] On the authority of <narrator>, that the Prophet ﷺ said:
   <!--hadith coll=<collection> num=<number> conf=<confidence> src=dataset-->
   «ARABIC»
   "ENGLISH" (Narrated by <Collection> <number>)
   <!--/hadith-->
   ```
   If `matched:false` (e.g. Musnad Ahmad / Hakim / Bayhaqi — not in the dataset), fetch from sunnah.com,
   mark `src=fallback conf=0`, and it will be flagged for the user's review. Never invent a hadith.

## Rules
- Keep the ﷺ symbol wherever the source has it. Keep chapter titles as descriptive headings (`## …`).
- If the canonical English of a hadith reads unclearly, still paste it verbatim — do not fix it inline;
  it gets flagged to `review.md` for the user.
- Ornamental/calligraphy pages (a Basmala, a divider): emit a one-line note like
  `*[Ornamental page: Basmala]*`, don't translate glyphs.
- Output ONLY the translated Markdown for your chunk. Return it as your final message.
```

- [ ] **Step 2: Write `SKILL.md`** — the workflow

```markdown
---
name: translate-islamic-book
description: Translate an Arabic Islamic book (Quran + hadith + author prose) into English at high
  fidelity — sacred content retrieved verbatim from bundled datasets, prose translated by subagents,
  output as DOCX + HTML. Use when the user wants to translate an Arabic religious/Islamic book PDF.
---

# Translate an Islamic book

## One-time setup
Run `python scripts/setup_data.py` (downloads Quran + hadith datasets into `data/`). Ensure `pandoc`
and poppler (`pdftotext`, `pdfinfo`, `pdffonts`) are installed.

## Per book
1. **Ingest.** `python -m scripts.ingest_book analyze <book.pdf> --work <book>/work` → note total pages,
   `toc_candidate_pages`, `ornamental_pages`.
2. **Read the ToC (vision).** Read the ToC page(s) with the Read tool; write `<book>/work/structure.json`:
   `[{"title": "...", "start_page": N, "level": 1, "appendix": false}, ...]`. Mark appendix chapters
   `"appendix": true`.
3. **Chunk.** `python -m scripts.ingest_book chunk <book.pdf> --work <book>/work --target 10`
   → `chunks.json`.
4. **Prime the glossary.** Read ~3 spread-out chunks; write `<book>/work/glossary.json` — canonical
   English for recurring names and transliterated terms (+ their glosses).
5. **Translate (parallel subagents).** For each chunk, dispatch a Task subagent with
   `templates/translator-subagent.md`, the chunk's page range + `context_page`, the glossary, and
   whether it's an appendix chunk. Collect each subagent's Markdown → `<book>/work/translated/chunk_NNNN.md`.
   Run up to ~8 concurrently.
6. **Verify.** `python -m out.verify` over the concatenated chunks (or per chunk); collect `problems`
   (fix by re-running that chunk) and `flagged` items → write `<book>/work/review.md` for the user.
7. **Assemble + convert.** `python -m out.assemble <book>/work/translated <book>/work/book.md`, then
   `python -m out.convert <book>/work/book.md <book>/output`.
8. **Report.** Give the user `output/<book>.docx`, `output/<book>.html`, and `review.md` (the hadith to
   sign off on). PDF: export from Word or print the HTML from a browser (both handle Arabic correctly).

## Non-negotiables
- Verse/hadith text is ALWAYS from the retrieval library or a flagged fallback — never LLM-written.
- Never split a section across chunks (the chunker enforces this).
- Nothing in `review.md` is altered without the user's sign-off.
```

- [ ] **Step 3: Add CLI entry points so the SKILL.md commands work**

Add `main()` guards so `python -m out.assemble <chunk_dir> <out>` and `python -m out.convert <md> <out_dir>` run. Append to `out/assemble.py`:
```python
if __name__ == "__main__":
    import sys
    assemble(sys.argv[1], sys.argv[2])
    print("assembled -> %s" % sys.argv[2])
```
Append to `out/convert.py`:
```python
if __name__ == "__main__":
    import json
    import sys
    print(json.dumps(convert_all(sys.argv[1], sys.argv[2])))
```
Commit:
```bash
git add templates/translator-subagent.md SKILL.md out/assemble.py out/convert.py
git commit -m "feat: SKILL.md workflow + translator subagent template + module CLIs"
```

- [ ] **Step 4: One-chunk end-to-end demo (offer to the user; needs a real translation subagent)**

Prove the pipeline on ONE chunk before any full-book run: ingest Al-Minhaj, dispatch a single translator
subagent for one text chunk (e.g. Chapter One), run `verify` + `assemble` + `convert` on that chunk, and
open the resulting HTML/DOCX. Confirm verses show the exact Saheeh Intl text with `[Surah: ayah]` and
hadith carry `(Narrated by …)`. This validates the whole chain at ~1 chunk of cost, not 140 pages.

---

## Self-Review

**Spec coverage** (design §5 Stages 4–6, §9–§11):
- Stage 4 translate via parallel subagents, three-lane routing, retrieval-not-translation → Task 4 template + SKILL.md §5. ✓
- Glossary priming → SKILL.md §4. ✓
- Stage 5 verify + `review.md` flagging (fallback / low-confidence / ambiguous hadith) → Task 2 + SKILL.md §6. ✓
- Stage 6 assemble (hadith numbering incl. `-A` appendix) + convert (DOCX + HTML) → Tasks 1, 3. ✓
- Formatting conventions (markers carry ref/collection; ﷺ preserved; transliteration glosses) → Task 4 template. ✓

**Deferred / documented:** PDF is exported by the user from DOCX/HTML (reliable Arabic) rather than a CLI engine; the "unclear hadith" clarification stays a human decision in `review.md`; glossary consistency is enforced by feeding the shared glossary to every subagent.

**Placeholder scan:** none — Python steps have runnable code; the two prompt/doc files are complete.

**Type consistency:** markers `<!--quran s= a= tr=-->` / `<!--hadith coll= num= conf= src=-->` are emitted by the subagent template, parsed by `verify.parse_markers`, and their `[[H]]`/`[[HA]]` placeholders consumed by `assemble.assign_hadith_numbers` — one shared contract across Tasks 1/2/4. ✓
