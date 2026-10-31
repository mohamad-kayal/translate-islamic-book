"""Is this install ready to use? Real lookups, not just file checks.

    python -m scripts.doctor

Exits 1 if anything a run needs is missing. Optional items only warn.
"""
import importlib.util
import os
import pathlib
import shutil
import sys

from retrieval.hadith_index import HadithIndex
from retrieval.quran_index import QuranIndex
from scripts.render_pdf import _chrome
from scripts.setup_data import DATA_DIR, check_manifest

REPO = pathlib.Path(__file__).resolve().parents[1]
REQUIRED_TOOLS = ("pandoc", "pdftotext", "pdfinfo", "pdffonts", "pdftoppm")


def checks():
    """[(name, ok, required, detail)]."""
    out = [("python >= 3.9", sys.version_info >= (3, 9), True, sys.version.split()[0])]
    for tool in REQUIRED_TOOLS:
        out.append((tool, shutil.which(tool) is not None, True, shutil.which(tool) or "not found"))
    try:
        chrome = _chrome()
    except Exception as e:
        chrome = None
        detail = str(e)
    else:
        detail = chrome
    out.append(("chrome (book PDFs)", bool(chrome), True, detail or "not found"))
    out.append(("yt-dlp (YouTube URLs)", importlib.util.find_spec("yt_dlp") is not None, False,
                "pip install -r requirements.txt"))

    problems = check_manifest(os.path.abspath(DATA_DIR))
    out.append(("datasets match MANIFEST.json", not problems, True,
                problems[0] if problems else "SHA-256 verified"))
    if problems:
        return out
    quran = QuranIndex.load()
    verse = quran.identify_span("الله لا إله إلا هو الحي القيوم لا تأخذه سنة ولا نوم")
    out.append(("qur'an lookup", bool(verse) and verse[:2] == (2, 255), True, str(verse)))
    hadith = HadithIndex.load()
    match = hadith.match("إنما الأعمال بالنيات")
    out.append(("hadith lookup", bool(match) and match["collection"] == "bukhari", True,
                "%s %s" % (match["collection"], match["number"]) if match else "no match"))
    out.append(("musnad ahmad", hadith.get("ahmad", 1) is not None, True,
                "%d hadith" % sum(e["collection"] == "ahmad" for e in hadith.entries)))

    linked = sorted(p.name for p in (REPO / "skills").iterdir() if (p / "SKILL.md").exists())
    home = pathlib.Path.home() / ".claude" / "skills"
    missing = [n for n in linked if not (home / n / "SKILL.md").exists()]
    out.append(("skills linked for Claude Code", not missing, False,
                "run ./install.sh: %s" % ", ".join(missing) if missing else ", ".join(linked)))
    return out


def main():
    failed = False
    for name, ok, required, detail in checks():
        label = "ok  " if ok else ("FAIL" if required else "warn")
        print("%s  %-32s %s" % (label, name, detail))
        failed = failed or (required and not ok)
    print("NOT READY" if failed else "READY")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
