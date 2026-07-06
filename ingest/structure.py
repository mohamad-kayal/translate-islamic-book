"""Section structure: locate the ToC, validate an agent-supplied section list, page ranges."""
import re
import subprocess

# 'املحتويات' is the same word as extracted by PDF text layers that scramble the
# lam-alef ligature order — common in Arabic PDFs.
TOC_MARKERS = ["محتويات", "املحتويات", "الفهرس", "فهرس", "Contents"]
_WEAK_MARKERS = ["جدول"]   # 'table' alone is prose-prone; needs a ToC-shaped page too
_BIDI_CTRL = re.compile("[‎‏‪-‮⁦-⁩]")
_NUMBER_LINE = re.compile(r"^[0-9٠-٩]{1,4}$")


def _page_text(pdf, p):
    out = subprocess.run(
        ["pdftotext", "-enc", "UTF-8", "-f", str(p), "-l", str(p), pdf, "-"],
        capture_output=True, text=True).stdout
    return _BIDI_CTRL.sub("", out or "")


def _toc_shaped(text):
    """A ToC page carries many standalone page-number lines."""
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    return sum(1 for ln in lines if _NUMBER_LINE.match(ln)) >= 5


def locate_toc_pages(pdf, scan_pages=12):
    """1-based pages that look like a ToC. Scans the first AND last `scan_pages`
    (Arabic books commonly put the fihris at the end) and extends each marker hit
    across adjacent ToC-shaped continuation pages (which carry no marker word)."""
    from .pages import page_count
    total = page_count(pdf)
    candidates = list(range(1, min(scan_pages, total) + 1))
    candidates += [p for p in range(max(1, total - scan_pages + 1), total + 1)
                   if p not in candidates]
    hits = []
    for p in candidates:
        text = _page_text(pdf, p)
        strong = any(m in text for m in TOC_MARKERS)
        weak = any(m in text for m in _WEAK_MARKERS) and _toc_shaped(text)
        if strong or weak:
            hits.append(p)
            nxt = p + 1
            while nxt <= total and nxt not in hits and _toc_shaped(_page_text(pdf, nxt)):
                hits.append(nxt)
                nxt += 1
    return sorted(set(hits))


def build_page_ranges(sections, total_pages):
    """Fill end_page for each section: ends the page before the next section starts;
    the last section ends at total_pages. Stable-sorted by start_page, so sections
    sharing a printed page keep their input (reading) order — the earlier one gets
    a zero-length range and the chunker keeps same-page sections together."""
    ordered = sorted(sections, key=lambda s: s["start_page"])   # sorted() is stable
    out = []
    for i, s in enumerate(ordered):
        if i + 1 < len(ordered):
            end = max(ordered[i + 1]["start_page"] - 1, s["start_page"] - 1)
            if ordered[i + 1]["start_page"] == s["start_page"]:
                end = s["start_page"]   # shared page belongs to both; chunker keeps them together
        else:
            end = total_pages
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
    for s in sections:
        if not (1 <= s["start_page"] <= total_pages):
            problems.append("section '%s' start_page %s out of range 1..%d"
                            % (s.get("title", "?"), s["start_page"], total_pages))
    return problems
