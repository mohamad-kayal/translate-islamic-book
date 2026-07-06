"""Per-page analysis: text vs ornamental classification + Quran-font detection."""
import os
import re
import subprocess

ORNAMENTAL_MAX_CHARS = 30   # fewer visible chars than this => ornamental/divider page
_WS = re.compile(r"\s+")


def _char_count(text):
    # letters + digits only: underscores (ruled notebook pages), punctuation and
    # invisible bidi controls are not content and must not defeat classification.
    return sum(1 for ch in _WS.sub("", text or "") if ch.isalnum())


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


def analyze_book(pdf):
    n = page_count(pdf)
    return {"pdf": os.path.abspath(pdf), "total_pages": n,
            "pages": [analyze_page(pdf, p) for p in range(1, n + 1)]}
