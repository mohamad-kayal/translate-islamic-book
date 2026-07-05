# PDF Ingestion — Implementation Plan (Plan 2 of 3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn a book PDF into a **chunk plan** — a list of page ranges that never split a section — plus a per-page manifest (text vs ornamental, Quran-font flag), so Plan 3's subagents can translate one coherent chunk at a time by reading the rendered pages.

**Architecture:** Pure-stdlib Python package `ingest/` wrapping poppler CLIs (`pdftotext`, `pdffonts`, `pdfinfo`). Deterministic pieces (page classification, section→page ranges, smart chunking) are unit-tested. The one non-deterministic step — reading the Table of Contents — is done by the orchestrating agent via **vision** (pdftotext garbles Arabic reading order, and these PDFs have no bookmark outline), then validated in Python. Page *content* is never extracted for translation here; Plan 3 subagents read the rendered pages directly.

**Tech Stack:** Python 3.9+, **standard library only** (`subprocess`, `json`, `re`, `argparse`); poppler CLIs (already installed). Dev/test: `pytest`.

## Global Constraints

- Python **3.9+**, **no third-party runtime deps**; poppler (`pdftotext`, `pdffonts`, `pdfinfo`) on PATH.
- **Never split a section across chunks** (the user's "don't separate chapter 5 that starts on page 51").
- Structure comes from the **ToC read by the agent (vision)** — verified live: neither target PDF has a bookmark outline; pdftotext garbles Arabic order. Python validates the agent's section list.
- Classification (verified live): a page with **< 30 non-space chars** is `ornamental` (calligraphy/divider — e.g. Anwar's Basmala on p4; 19 such pages in Anwar), else `text`. A page whose fonts include **`KFGQPC`** (King Fahd Complex Quran fonts) is flagged `quran_font: true`.
- ToC location (verified live): both books' ToC is on p5, findable by the markers محتويات / المحتويات / جدول / فهرس / Contents.
- Work artifacts live in a per-book `work/` dir (gitignored): `manifest.json`, `structure.json` (agent-written), `chunks.json`.

## File Structure

```
translate-islamic-book/
  ingest/
    __init__.py
    pages.py        # per-page analysis: char count, Quran-font flag, classification
    structure.py    # locate ToC, validate an agent-supplied section list, compute page ranges
    chunk.py        # smart chunker: sections -> chunks that never split a section
  scripts/
    ingest_book.py  # CLI: `analyze` (Python) then `chunk` (Python, given agent's structure.json)
  tests/
    test_pages.py
    test_structure.py
    test_chunk.py
    test_ingest_integration.py   # integration; runs against the real Arabic PDFs, skips if absent
```

---

### Task 1: Page analysis + classification

**Files:**
- Create: `translate-islamic-book/ingest/__init__.py` (empty), `translate-islamic-book/ingest/pages.py`
- Create: `translate-islamic-book/tests/test_pages.py`

**Interfaces:**
- Produces: `classify(char_count, threshold=30) -> str`, `page_count(pdf) -> int`, `analyze_page(pdf, page) -> dict`, `analyze_book(pdf) -> dict`. `analyze_book` returns `{"pdf","total_pages","pages":[{page,chars,classification,quran_font}]}`.

- [ ] **Step 1: Write the failing test** — `tests/test_pages.py`

```python
from ingest import pages


def test_classify_threshold():
    assert pages.classify(0) == "ornamental"
    assert pages.classify(29) == "ornamental"
    assert pages.classify(30) == "text"
    assert pages.classify(2000) == "text"


def test_char_count_ignores_whitespace():
    assert pages._char_count("  ab \n c d\t") == "abcd".__len__()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd translate-islamic-book && . .venv/bin/activate && python -m pytest tests/test_pages.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'ingest'`

- [ ] **Step 3: Write minimal implementation** — `ingest/pages.py`

```python
"""Per-page analysis: text vs ornamental classification + Quran-font detection."""
import os
import re
import subprocess

ORNAMENTAL_MAX_CHARS = 30   # fewer visible chars than this => ornamental/divider page
_WS = re.compile(r"\s+")


def _char_count(text):
    return len(_WS.sub("", text or ""))


def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True).stdout


def _page_text(pdf, page):
    return _run(["pdftotext", "-enc", "UTF-8", "-f", str(page), "-l", str(page), pdf, "-"])


def _page_has_quran_font(pdf, page):
    return "KFGQPC" in _run(["pdffonts", "-f", str(page), "-l", str(page), pdf])


def classify(char_count, threshold=ORNAMENTAL_MAX_CHARS):
    return "ornamental" if char_count < threshold else "text"


def page_count(pdf):
    m = re.search(r"^Pages:\s+(\d+)", _run(["pdfinfo", pdf]), re.M)
    if not m:
        raise RuntimeError("could not read page count from pdfinfo: %s" % pdf)
    return int(m.group(1))


def analyze_page(pdf, page):
    chars = _char_count(_page_text(pdf, page))
    return {"page": page, "chars": chars,
            "classification": classify(chars),
            "quran_font": _page_has_quran_font(pdf, page)}


def analyze_book(pdf):
    n = page_count(pdf)
    return {"pdf": os.path.abspath(pdf), "total_pages": n,
            "pages": [analyze_page(pdf, p) for p in range(1, n + 1)]}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_pages.py -q`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add ingest/__init__.py ingest/pages.py tests/test_pages.py
git commit -m "feat(ingest): per-page classification + Quran-font detection"
```

---

### Task 2: Structure — ToC location, validation, page ranges

**Files:**
- Create: `translate-islamic-book/ingest/structure.py`
- Create: `translate-islamic-book/tests/test_structure.py`

**Interfaces:**
- Produces: `locate_toc_pages(pdf, scan_pages=12) -> list[int]`, `build_page_ranges(sections, total_pages) -> list[dict]` (adds `end_page`), `validate_structure(sections, total_pages) -> list[str]` (problems; empty = ok). A `section` is `{"title","start_page","level"}`.

- [ ] **Step 1: Write the failing test** — `tests/test_structure.py`

```python
from ingest import structure as st


def test_build_page_ranges_fills_ends():
    secs = [{"title": "A", "start_page": 1, "level": 1},
            {"title": "B", "start_page": 5, "level": 1},
            {"title": "C", "start_page": 9, "level": 1}]
    out = st.build_page_ranges(secs, total_pages=12)
    assert [(s["start_page"], s["end_page"]) for s in out] == [(1, 4), (5, 8), (9, 12)]


def test_build_page_ranges_sorts_by_start():
    secs = [{"title": "B", "start_page": 5, "level": 1},
            {"title": "A", "start_page": 1, "level": 1}]
    out = st.build_page_ranges(secs, total_pages=8)
    assert [s["title"] for s in out] == ["A", "B"]
    assert out[0]["end_page"] == 4 and out[1]["end_page"] == 8


def test_validate_catches_problems():
    assert st.validate_structure([], 10) == ["no sections"]
    bad = [{"title": "A", "start_page": 1, "level": 1},
           {"title": "B", "start_page": 99, "level": 1}]
    probs = st.validate_structure(bad, total_pages=10)
    assert any("out of range" in p for p in probs)


def test_validate_ok():
    good = [{"title": "A", "start_page": 1, "level": 1},
            {"title": "B", "start_page": 5, "level": 1}]
    assert st.validate_structure(good, total_pages=10) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_structure.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'ingest.structure'`

- [ ] **Step 3: Write minimal implementation** — `ingest/structure.py`

```python
"""Section structure: locate the ToC, validate an agent-supplied section list, page ranges."""
import re
import subprocess

TOC_MARKERS = ["المحتويات", "محتويات", "الفهرس", "فهرس", "جدول", "Contents"]


def locate_toc_pages(pdf, scan_pages=12):
    """Return 1-based page numbers among the first `scan_pages` that look like a ToC."""
    hits = []
    for p in range(1, scan_pages + 1):
        out = subprocess.run(
            ["pdftotext", "-enc", "UTF-8", "-f", str(p), "-l", str(p), pdf, "-"],
            capture_output=True, text=True).stdout
        if any(m in out for m in TOC_MARKERS):
            hits.append(p)
    return hits


def build_page_ranges(sections, total_pages):
    """Fill end_page for each section: ends the page before the next section starts;
    the last section ends at total_pages. Input is sorted by start_page first."""
    ordered = sorted(sections, key=lambda s: s["start_page"])
    out = []
    for i, s in enumerate(ordered):
        end = ordered[i + 1]["start_page"] - 1 if i + 1 < len(ordered) else total_pages
        out.append(dict(s, end_page=end))
    return out


def validate_structure(sections, total_pages):
    """Return a list of problems (empty list = valid)."""
    if not sections:
        return ["no sections"]
    problems = []
    starts = [s["start_page"] for s in sections]
    if starts != sorted(starts):
        problems.append("section start pages are not in increasing order")
    if len(set(starts)) != len(starts):
        problems.append("duplicate section start pages")
    for s in sections:
        if not (1 <= s["start_page"] <= total_pages):
            problems.append("section '%s' start_page %s out of range 1..%d"
                            % (s.get("title", "?"), s["start_page"], total_pages))
    return problems
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_structure.py -q`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add ingest/structure.py tests/test_structure.py
git commit -m "feat(ingest): ToC location, structure validation, page-range computation"
```

---

### Task 3: Smart chunker (never split a section)

**Files:**
- Create: `translate-islamic-book/ingest/chunk.py`
- Create: `translate-islamic-book/tests/test_chunk.py`

**Interfaces:**
- Produces: `smart_chunk(sections, target_pages=10) -> list[dict]`. Input sections have `start_page`/`end_page`. Each chunk: `{"sections":[titles], "start_page", "end_page", "page_count", "context_page"}` (`context_page` = the page just before the chunk, for continuity, or `null` at the book start).

- [ ] **Step 1: Write the failing test** — `tests/test_chunk.py`

```python
from ingest.chunk import smart_chunk


def _secs(sizes):
    # build contiguous sections of the given page-sizes, starting at page 1
    out, start = [], 1
    for i, n in enumerate(sizes):
        out.append({"title": "S%d" % i, "start_page": start, "end_page": start + n - 1})
        start += n
    return out


def test_packs_whole_sections_under_target():
    chunks = smart_chunk(_secs([3, 3, 3, 3]), target_pages=7)
    assert [c["page_count"] for c in chunks] == [6, 6]
    assert [c["sections"] for c in chunks] == [["S0", "S1"], ["S2", "S3"]]


def test_oversized_section_becomes_its_own_chunk():
    chunks = smart_chunk(_secs([4, 15, 4]), target_pages=10)
    assert [c["page_count"] for c in chunks] == [4, 15, 4]     # the 15-page section is never split


def test_covers_all_pages_without_gaps_or_overlap():
    secs = _secs([3, 3, 3, 3])
    chunks = smart_chunk(secs, target_pages=7)
    pages = []
    for c in chunks:
        pages.extend(range(c["start_page"], c["end_page"] + 1))
    assert pages == list(range(1, 13))                          # 1..12, contiguous, no repeats


def test_context_page_is_prev_page_or_none():
    chunks = smart_chunk(_secs([5, 5]), target_pages=5)
    assert chunks[0]["context_page"] is None                   # first chunk starts at page 1
    assert chunks[1]["context_page"] == 5                       # page before chunk 2's start (6)


def test_single_section():
    chunks = smart_chunk(_secs([8]), target_pages=10)
    assert len(chunks) == 1 and chunks[0]["page_count"] == 8
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_chunk.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'ingest.chunk'`

- [ ] **Step 3: Write minimal implementation** — `ingest/chunk.py`

```python
"""Smart chunking: pack whole sections into chunks, never splitting a section."""


def _close(secs):
    start, end = secs[0]["start_page"], secs[-1]["end_page"]
    return {
        "sections": [s["title"] for s in secs],
        "start_page": start,
        "end_page": end,
        "page_count": end - start + 1,
        "context_page": start - 1 if start > 1 else None,
    }


def smart_chunk(sections, target_pages=10):
    """sections: [{title, start_page, end_page}] in reading order. Returns chunks, each a
    run of whole sections whose combined length stays near target_pages (a single section
    longer than target becomes its own chunk). A section is never split across chunks."""
    chunks, cur, cur_pages = [], [], 0
    for sec in sections:
        sec_pages = sec["end_page"] - sec["start_page"] + 1
        if cur and cur_pages + sec_pages > target_pages:
            chunks.append(_close(cur))
            cur, cur_pages = [], 0
        cur.append(sec)
        cur_pages += sec_pages
    if cur:
        chunks.append(_close(cur))
    return chunks
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_chunk.py -q`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add ingest/chunk.py tests/test_chunk.py
git commit -m "feat(ingest): section-boundary smart chunker (never splits a section)"
```

---

### Task 4: Ingest CLI orchestrator + integration

**Files:**
- Create: `translate-islamic-book/scripts/ingest_book.py`
- Create: `translate-islamic-book/tests/test_ingest_integration.py`

**Interfaces:**
- CLI: `python -m scripts.ingest_book analyze <pdf> --work <dir>` writes `<dir>/manifest.json`, prints `total_pages`, `toc_candidate_pages`, `ornamental_pages`. `python -m scripts.ingest_book chunk <pdf> --work <dir> [--target N]` reads `<dir>/structure.json` (agent-written), validates it, writes `<dir>/chunks.json`.

- [ ] **Step 1: Write the failing test** — `tests/test_ingest_integration.py`

```python
import json
import os
import subprocess
import sys

import pytest

pytestmark = pytest.mark.integration
# Al-Minhaj Arabic source lives beside the skill repo.
SRC = os.path.join(os.path.dirname(__file__), "..", "..", "Arabic", "Alminhaj.pdf")


def _need():
    if not os.path.exists(SRC):
        pytest.skip("Al-Minhaj source not found at %s" % SRC)


def _run(args, **kw):
    env = dict(os.environ, PYTHONPATH=os.getcwd())
    return subprocess.run([sys.executable, "-m", "scripts.ingest_book"] + args,
                          capture_output=True, text=True, env=env, **kw)


def test_analyze_real_book(tmp_path):
    _need()
    r = _run(["analyze", SRC, "--work", str(tmp_path)])
    assert r.returncode == 0, r.stderr
    manifest = json.load(open(tmp_path / "manifest.json", encoding="utf-8"))
    assert manifest["total_pages"] == 140
    assert "toc_candidate_pages: [5]" in r.stdout or "5" in r.stdout
    # at least one ornamental page and one Quran-font page exist
    assert any(p["classification"] == "ornamental" for p in manifest["pages"])
    assert any(p["quran_font"] for p in manifest["pages"])


def test_chunk_from_structure(tmp_path):
    _need()
    # a tiny hand-made structure (3 sections) to exercise the chunk path end-to-end
    struct = [{"title": "Ch1", "start_page": 15, "level": 1},
              {"title": "Ch2", "start_page": 20, "level": 1},
              {"title": "Ch3", "start_page": 29, "level": 1}]
    (tmp_path / "structure.json").write_text(json.dumps(struct, ensure_ascii=False), encoding="utf-8")
    r = _run(["chunk", SRC, "--work", str(tmp_path), "--target", "8"])
    assert r.returncode == 0, r.stderr
    chunks = json.load(open(tmp_path / "chunks.json", encoding="utf-8"))
    assert chunks and all("sections" in c and c["page_count"] >= 1 for c in chunks)
    # no chunk boundary splits a section: every chunk's pages are whole sections
    assert chunks[0]["start_page"] == 15
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_ingest_integration.py -q -m integration`
Expected: FAIL — `No module named 'scripts.ingest_book'`

- [ ] **Step 3: Write minimal implementation** — `scripts/ingest_book.py`

```python
"""Ingest a book PDF into a chunk plan.

Workflow (the agent supplies the ToC read between the two Python steps):
  1. analyze SOURCE.pdf --work WORK   -> WORK/manifest.json  (+ prints ToC candidate pages)
  2. agent reads the ToC page(s) by vision and writes WORK/structure.json:
       [{"title": "...", "start_page": N, "level": 1}, ...]
  3. chunk SOURCE.pdf --work WORK     -> WORK/chunks.json
"""
import argparse
import json
import os
import sys

from ingest import chunk as chunker
from ingest import pages, structure


def _write(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def _analyze(args):
    manifest = pages.analyze_book(args.pdf)
    os.makedirs(args.work, exist_ok=True)
    _write(os.path.join(args.work, "manifest.json"), manifest)
    orn = [p["page"] for p in manifest["pages"] if p["classification"] == "ornamental"]
    print("total_pages: %d" % manifest["total_pages"])
    print("toc_candidate_pages: %s" % structure.locate_toc_pages(args.pdf))
    print("ornamental_pages: %s" % orn)
    print("wrote %s" % os.path.join(args.work, "manifest.json"))
    return 0


def _chunk(args):
    with open(os.path.join(args.work, "structure.json"), encoding="utf-8") as f:
        sections = json.load(f)
    total = pages.page_count(args.pdf)
    problems = structure.validate_structure(sections, total)
    if problems:
        print("STRUCTURE INVALID:", file=sys.stderr)
        for p in problems:
            print("  - " + p, file=sys.stderr)
        return 2
    ranged = structure.build_page_ranges(sections, total)
    chunks = chunker.smart_chunk(ranged, target_pages=args.target)
    _write(os.path.join(args.work, "chunks.json"), chunks)
    print("wrote %d chunks -> %s" % (len(chunks), os.path.join(args.work, "chunks.json")))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description="Ingest a book PDF into a chunk plan.")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("analyze")
    a.add_argument("pdf")
    a.add_argument("--work", required=True)
    a.set_defaults(fn=_analyze)
    c = sub.add_parser("chunk")
    c.add_argument("pdf")
    c.add_argument("--work", required=True)
    c.add_argument("--target", type=int, default=10)
    c.set_defaults(fn=_chunk)
    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_ingest_integration.py -q -m integration`
Expected: PASS (2 passed) when the Arabic source exists; SKIPPED otherwise.

- [ ] **Step 5: Run the full suite (unit + integration) to confirm no regression**

Run: `python -m pytest -q`
Expected: PASS — Plan 1's 30 tests + Plan 2's tests, 0 failures.

- [ ] **Step 6: Commit**

```bash
git add scripts/ingest_book.py tests/test_ingest_integration.py
git commit -m "feat(ingest): ingest_book CLI (analyze + chunk) with real-book integration test"
```

---

## Self-Review

**Spec coverage** (design §5 Stages 1–3):
- Stage 1 extract & classify (text vs ornamental, Quran-font signal) → Task 1. ✓
- Stage 2 map structure (ToC-derived section tree with page ranges) → Task 2 + the agent's vision ToC read (documented in the CLI workflow). ✓
- Stage 3 smart chunk (never split a section, ~target pages, continuity via `context_page`) → Task 3. ✓
- Orchestration + work artifacts (`manifest.json`, `structure.json`, `chunks.json`) → Task 4. ✓

**Deliberately deferred:** rendering pages to images (Plan 3 subagents read pages via the Read tool directly); the vision ToC read itself is an agent step, not Python (validated by `validate_structure`).

**Placeholder scan:** none — every step has runnable code + commands.

**Type consistency:** a `section` is `{title, start_page, level}` (+`end_page` after `build_page_ranges`) everywhere; `smart_chunk` consumes `start_page`/`end_page` and emits `{sections, start_page, end_page, page_count, context_page}`; the CLI reads/writes those shapes. `analyze_book` → `{pdf, total_pages, pages:[{page,chars,classification,quran_font}]}` consistent across Task 1/4. ✓

**Known follow-ups for Plan 3:** the agent's ToC read must emit the `structure.json` shape; ornamental pages (e.g. Basmala) get a short semantic note rather than translation; `context_page` is read for continuity but not re-translated.
