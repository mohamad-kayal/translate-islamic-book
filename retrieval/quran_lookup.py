"""High-level Quran retrieval + JSON CLI (called by translation subagents)."""
import argparse
import json

from .quran_index import QuranIndex
from .refs import format_quran_ref_ar, format_quran_ref_en

_INDEX = None


def _index():
    global _INDEX
    if _INDEX is None:
        _INDEX = QuranIndex.load()
    return _INDEX


def lookup(arabic_query, translation="saheeh"):
    idx = _index()
    span = idx.identify_span(arabic_query)
    if span is None:
        return {"matched": False}
    s, a0, a1, cov = span
    verses = [idx.get_verse(s, a) for a in range(a0, a1 + 1)]
    return {
        "matched": True,
        "surah": s, "ayah_start": a0, "ayah_end": a1, "coverage": cov,
        "arabic": " ".join(v["arabic"] for v in verses),
        "english_saheeh": " ".join(v["saheeh"] for v in verses),
        "english_clear": " ".join(v["clear"] for v in verses),
        "ref_en": format_quran_ref_en(s, a0, a1),
        "ref_ar": format_quran_ref_ar(s, a0, a1),
    }


def main(argv=None):
    p = argparse.ArgumentParser(description="Identify + retrieve Quran verse(s) from Arabic.")
    p.add_argument("--match", required=True, help="Arabic quotation to identify")
    args = p.parse_args(argv)
    print(json.dumps(lookup(args.match), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
