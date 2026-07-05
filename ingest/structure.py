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
    the last section ends at total_pages. Sorted by start_page first."""
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
