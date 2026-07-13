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
    spans, total = idx.identify_spans(arabic_query)
    if not spans:
        out = {"matched": False}
        near = idx.nearest(arabic_query)
        if near:
            # No verbatim span (usually one misread word): show the closest ayat so
            # the caller can correct its reading instead of retrying blind.
            out["nearest"] = [
                {"surah": s, "ayah": a, "score": sc, "arabic": idx.get_verse(s, a)["arabic"]}
                for s, a, sc in near]
        return out
    s, a0, a1 = spans[0]
    verses = [idx.get_verse(s, a) for a in range(a0, a1 + 1)]
    return {
        "matched": True,
        "surah": s, "ayah_start": a0, "ayah_end": a1, "coverage": 1.0,
        # A repeated (mutashabih) phrase exists at every location below; the FIRST is
        # only a default — the author's citation or the context must pick when n > 1.
        "n_locations": total,
        "locations": [{"surah": s2, "ayah_start": b0, "ayah_end": b1,
                       "ref_en": format_quran_ref_en(s2, b0, b1)}
                      for s2, b0, b1 in spans],
        "locations_truncated": total > len(spans),
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
