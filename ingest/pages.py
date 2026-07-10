"""Per-page analysis: text vs ornamental classification + Quran-font detection."""
import os
import re
import subprocess

ORNAMENTAL_MAX_CHARS = 30   # fewer visible chars than this => ornamental/divider page
_WS = re.compile(r"\s+")


_TATWEEL = "ـ"   # kashida — used to draw ruled "notes" pages; counts as alnum but isn't content


def _char_count(text):
    # letters + digits only: underscores AND tatweel/kashida rules (ruled note pages),
    # punctuation, and invisible bidi controls are not content and must not defeat
    # ornamental classification.
    return sum(1 for ch in _WS.sub("", text or "") if ch.isalnum() and ch != _TATWEEL)


def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True).stdout


def _page_text(pdf, page):
    return _run(["pdftotext", "-enc", "UTF-8", "-f", str(page), "-l", str(page), pdf, "-"])


def _page_has_quran_font(pdf, page):
    # KFGQPC = King Fahd Complex fonts; QCF_ = Quran-Complex per-page mushaf fonts.
    fonts = _run(["pdffonts", "-f", str(page), "-l", str(page), pdf])
    return "KFGQPC" in fonts or "QCF_" in fonts


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


def _all_pages_text(pdf, n):
    """Per-page texts from ONE whole-document pdftotext call (pages split on the
    form-feeds it emits) — or None when the count disagrees (a text layer with
    embedded form-feeds), in which case the caller re-extracts page by page."""
    parts = _run(["pdftotext", "-enc", "UTF-8", pdf, "-"]).split("\f")
    if len(parts) == n + 1 and not parts[-1].strip():   # trailing \f after last page
        parts = parts[:n]
    return parts if len(parts) == n else None


def analyze_book(pdf):
    n = page_count(pdf)
    texts = _all_pages_text(pdf, n)
    out = []
    for p in range(1, n + 1):
        chars = _char_count(texts[p - 1] if texts is not None else _page_text(pdf, p))
        out.append({"page": p, "chars": chars, "classification": classify(chars),
                    "quran_font": _page_has_quran_font(pdf, p)})
    return {"pdf": os.path.abspath(pdf), "total_pages": n, "pages": out}
