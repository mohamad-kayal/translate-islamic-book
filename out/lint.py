"""Deterministic lint for translated chunks and the assembled book.

`out.verify` guards the SACRED text (wording verbatim vs the datasets); lint guards
the fabric around it — the failure classes parallel translator subagents actually
produce: duplicated headings at chunk seams, heading-level drift, untranslated
Arabic remnants, transliteration drift (sun-letter assimilation), broken markers or
footnotes, and silently-short chunks (possible omissions). Problems would corrupt
the output; warnings need judgment and go to review.md. A report, not a gate:
always exits 0.

    python -m out.lint <book>/work [--glossary <book>/work/glossary.json]
"""
import argparse
import glob
import json
import os
import re
import statistics

from out.verify import _check_balance

_QURAN_BLOCK = re.compile(r"<!--quran\s[^>]*-->.*?<!--/quran-->", re.S)
_HADITH_BLOCK = re.compile(r"<!--hadith\s[^>]*-->.*?<!--/hadith-->", re.S)
_COMMENT = re.compile(r"<!--.*?-->", re.S)
_AR_SPAN = re.compile(r"\[[^\]]*\]\{[^}]*lang=ar[^}]*\}")
_ARABIC = re.compile(r"[؀-ۿ][؀-ۿ\s]*")
_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*$", re.M)
_SPACED_MARKER = re.compile(r"<!--\s+/?(?:quran|hadith)\b")
_OPENER = re.compile(r"<!--(quran|hadith)\s+([^>]*?)-->")
_ATTRS = re.compile(r"(\w+)=(\S+)")
_REQUIRED = {"quran": ("s", "a", "tr"), "hadith": ("coll", "num", "conf", "src")}
_GLOSS = re.compile(r"\*([^*\n]+)\*\s*\(\[")
# Sun-letter assimilated article (as-Sa'di, ar-Rahman, an-Nawawi…): house style is
# al- with NO assimilation. Requires a capitalized next word so English words
# ("as-is") never match.
_SUN = re.compile(r"\b[aA](?:sh|th|dh|s|r|n|t|d|z)-[A-Z][\w''ʿʾ\-]*")
_PLACEHOLDER = re.compile(r"\[\[HA?\]\]")
_WORD = re.compile(r"[A-Za-z][A-Za-z''\-]*")
_FOOTNOTE_OPEN = re.compile(r"\^\[")

# A chunk whose words-per-source-char ratio falls below this fraction of the book
# median likely dropped content (a page or paragraphs) — the scariest silent failure.
_RATIO_FLOOR = 0.7


def _strip(pattern, text):
    """Blank out matches but keep newlines so reported line numbers stay true."""
    return pattern.sub(lambda m: "\n" * m.group(0).count("\n"), text)


def _headings(text):
    return [(len(m.group(1)), m.group(2)) for m in _HEADING.finditer(text)]


def _unclosed_footnotes(text):
    """Byte offsets of ^[ openers whose bracket never closes (depth-walked)."""
    bad = []
    for m in _FOOTNOTE_OPEN.finditer(text):
        depth, closed = 1, False
        for ch in text[m.end():]:
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    closed = True
                    break
        if not closed:
            bad.append(m.start())
    return bad


def _known_translits(glossary):
    known = set()
    for v in (glossary.get("terms") or {}).values():
        if isinstance(v, dict) and v.get("translit"):
            known.add(v["translit"].casefold())
    for v in (glossary.get("names") or {}).values():
        if isinstance(v, str) and v:
            known.add(v.casefold())
            known.add(v.split(" (")[0].casefold())
    # cited-work titles: recognized for drift-checking but NOT emitted in the
    # back-of-book Glossary appendix (append_glossary reads `terms` only)
    for v in (glossary.get("works") or {}).values():
        if isinstance(v, str) and v:
            known.add(v.casefold())
            known.add(v.split(" (")[0].casefold())
        elif isinstance(v, dict) and v.get("translit"):
            known.add(v["translit"].casefold())
    return known


def _chunk_findings(name, text, glossary=None):
    problems, warnings = [], []

    # --- problems: things that would corrupt assembly/verify/output
    bal = []
    _check_balance(text, bal)
    problems += ["%s: %s" % (name, b) for b in bal]
    for m in _SPACED_MARKER.finditer(text):
        problems.append("%s: malformed marker %r — no space allowed after <!--"
                        % (name, m.group(0)))
    for kind, attrs_raw in _OPENER.findall(text):
        attrs = dict(_ATTRS.findall(attrs_raw))
        missing = [k for k in _REQUIRED[kind] if k not in attrs]
        if missing:
            problems.append("%s: %s marker missing attrs: %s"
                            % (name, kind, ", ".join(missing)))

    blocked = _strip(_HADITH_BLOCK, _strip(_QURAN_BLOCK, text))
    for pos in _unclosed_footnotes(blocked):
        line = blocked.count("\n", 0, pos) + 1
        problems.append("%s: unclosed footnote ^[ at line %d" % (name, line))

    # --- warnings: prose-level drift for review.md (sacred block bodies excluded —
    # they are pasted dataset text, verify's jurisdiction)
    if glossary is not None:
        known = _known_translits(glossary)
        for m in _GLOSS.finditer(blocked):
            translit = m.group(1).strip()
            if _WORD.search(translit) and translit.casefold() not in known:
                warnings.append("%s: glossed term *%s* is not in the glossary — "
                                "harvest it or fix the drift" % (name, translit))

    levels = _headings(text)
    for (l1, t1), (l2, t2) in zip(levels, levels[1:]):
        if l2 > l1 + 1:
            warnings.append("%s: heading level jump %s -> %s at '%s'"
                            % (name, "#" * l1, "#" * l2, t2))

    prose = _strip(_COMMENT, _strip(_AR_SPAN, blocked))
    arabic_hits = []
    for i, line in enumerate(prose.split("\n"), 1):
        m = _ARABIC.search(line)
        if m:
            arabic_hits.append((i, m.group(0).strip()))
    for i, snippet in arabic_hits[:3]:
        warnings.append("%s: Arabic outside markers/lang=ar spans (line %d): %s"
                        % (name, i, snippet[:60]))
    if len(arabic_hits) > 3:
        warnings.append("%s: ...and %d more Arabic remnants"
                        % (name, len(arabic_hits) - 3))

    for m in sorted(set(_SUN.findall(prose))):
        warnings.append("%s: sun-letter assimilation '%s' — house style is al- "
                        "(no assimilation)" % (name, m))

    n_open, n_close = prose.count("«"), prose.count("»")
    if n_open != n_close:
        warnings.append("%s: unbalanced «» in prose (%d « vs %d »)"
                        % (name, n_open, n_close))
    if "�" in prose:
        warnings.append("%s: U+FFFD replacement character in prose" % name)

    return problems, warnings


def lint_chunks(chunk_texts, glossary=None):
    """chunk_texts: ordered [(name, text)]. Per-chunk checks + seam checks."""
    problems, warnings = [], []
    for name, text in chunk_texts:
        p, w = _chunk_findings(name, text, glossary=glossary)
        problems += p
        warnings += w
    for (name_a, a), (name_b, b) in zip(chunk_texts, chunk_texts[1:]):
        ha, hb = _headings(a), _headings(b)
        if ha and hb and ha[-1][1].casefold() == hb[0][1].casefold():
            warnings.append("duplicate heading at seam: %s ends and %s begins with "
                            "'%s'" % (name_a, name_b, hb[0][1]))
    return {"problems": problems, "warnings": warnings}


def lint_book(book_text):
    """Assembled-book checks: what assembly should have consumed or produced."""
    problems = []
    for m in sorted(set(_PLACEHOLDER.findall(book_text))):
        problems.append("book.md: leftover hadith placeholder %s — assembly should "
                        "have numbered or stripped it" % m)
    bal = []
    _check_balance(book_text, bal)
    problems += ["book.md: %s" % b for b in bal]
    blocked = _strip(_HADITH_BLOCK, _strip(_QURAN_BLOCK, book_text))
    for pos in _unclosed_footnotes(blocked):
        problems.append("book.md: unclosed footnote ^[ at line %d"
                        % (blocked.count("\n", 0, pos) + 1))
    return {"problems": problems, "warnings": []}


def completeness_warnings(chunk_texts, chunks, manifest):
    """Flag chunks whose English-words per source-char ratio is a low outlier —
    the cheap machine signal for a silently dropped page or paragraph."""
    chars_by_page = {p["page"]: p["chars"] for p in manifest.get("pages", [])
                     if p.get("classification") == "text"}
    # Pair by the file's chunk NUMBER, not by position — during a resumed run the
    # translated/ dir can have gaps, and a positional zip would misattribute every
    # file after the first missing chunk.
    by_num = {}
    for name, text in chunk_texts:
        m = re.search(r"chunk_(\d+)", name)
        if m:
            by_num[int(m.group(1))] = (name, text)
    ratios = []
    for i, chunk in enumerate(chunks, 1):
        if i not in by_num:
            continue
        name, text = by_num[i]
        src = sum(chars_by_page.get(p, 0)
                  for p in range(chunk["start_page"], chunk["end_page"] + 1))
        if src <= 0:
            continue
        words = len(_WORD.findall(_strip(_COMMENT, text)))
        ratios.append((name, words / src))
    if len(ratios) < 2:
        return []
    median = statistics.median(r for _, r in ratios)
    if median <= 0:
        return []
    return ["%s: possible omission — %.2f words/char vs book median %.2f "
            "(translated far less than its pages carry; re-check page by page)"
            % (name, r, median)
            for name, r in ratios if r < _RATIO_FLOOR * median]


def lint(work_dir, glossary_path=None):
    paths = sorted(glob.glob(os.path.join(work_dir, "translated", "chunk_*.md")))
    chunk_texts = []
    for p in paths:
        with open(p, encoding="utf-8") as f:
            chunk_texts.append((os.path.basename(p), f.read()))
    glossary = None
    if glossary_path:
        with open(glossary_path, encoding="utf-8") as f:
            glossary = json.load(f)
    result = lint_chunks(chunk_texts, glossary=glossary)
    checked = {"chunks": len(chunk_texts), "book": False, "ratio": False}

    book_path = os.path.join(work_dir, "book.md")
    if os.path.exists(book_path):
        with open(book_path, encoding="utf-8") as f:
            b = lint_book(f.read())
        result["problems"] += b["problems"]
        result["warnings"] += b["warnings"]
        checked["book"] = True

    chunks_path = os.path.join(work_dir, "chunks.json")
    manifest_path = os.path.join(work_dir, "manifest.json")
    if os.path.exists(chunks_path) and os.path.exists(manifest_path):
        with open(chunks_path, encoding="utf-8") as f:
            chunks = json.load(f)
        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)
        result["warnings"] += completeness_warnings(chunk_texts, chunks, manifest)
        checked["ratio"] = True

    result["checked"] = checked
    return result


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="Lint translated chunks + assembled book (see module docstring).")
    ap.add_argument("work_dir", help="the run's work directory (contains translated/)")
    ap.add_argument("--glossary", help="the book's glossary.json (enables gloss checks)")
    args = ap.parse_args()
    print(json.dumps(lint(args.work_dir, glossary_path=args.glossary),
                     ensure_ascii=False, indent=2))
