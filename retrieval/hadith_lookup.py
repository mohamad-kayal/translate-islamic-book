"""High-level hadith retrieval + JSON CLI (called by translation subagents)."""
import argparse
import json

from .hadith_index import HadithIndex

_INDEX = None


def _index():
    global _INDEX
    if _INDEX is None:
        _INDEX = HadithIndex.load()
    return _INDEX


def match(arabic_query, min_conf=0.6, prefer=None):
    """matched:true + the entry, or matched:false — with `nearest` (the best
    sub-threshold candidate) when one exists, so a subagent can correct its
    reading of the page instead of retrying blind."""
    r = _index().match(arabic_query, min_conf=0.0, prefer=prefer)
    if r is None:
        return {"matched": False}
    if r["confidence"] < min_conf:
        return {"matched": False,
                "nearest": {"collection": r["collection"], "number": r["number"],
                            "confidence": r["confidence"],
                            "arabic": r["arabic"][:200]}}
    out = dict(r, matched=True)
    if not r["english"].strip():
        out["english_missing"] = ("no published English in the dataset for this hadith — "
                                  "render the matn yourself and mark the block src=arabic")
    elif "�" in r["english"]:
        out["english_warning"] = ("dataset English contains U+FFFD replacement "
                                  "characters — paste verbatim and flag for review")
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description="Match an Arabic hadith matn to the dataset.")
    p.add_argument("--match", required=True)
    p.add_argument("--min-conf", type=float, default=0.6)
    p.add_argument("--prefer", default=None, metavar="COLLECTION",
                   help="the collection the AUTHOR cites (takhrij) — wins ties; "
                        "an unbundled collection is a harmless no-op")
    args = p.parse_args(argv)
    print(json.dumps(match(args.match, args.min_conf, prefer=args.prefer),
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
