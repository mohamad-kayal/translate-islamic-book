"""Re-check a book's unverified hadith after the datasets grow.

    python -m scripts.recheck_fallbacks runs/<slug> [--write]

A `src=fallback` hadith whose Arabic now matches a dataset entry becomes `src=arabic`
(`src=dataset` when its English matches too). Only the marker changes: the author's visible
citation stays, and the old number moves to `cite=` so the book's hadith index keeps it.
Reports without --write.
"""
import argparse
import glob
import json
import os
import re

from out.verify import _hadith_key, _arabic_of, english_of
from retrieval.hadith_index import HadithIndex
from retrieval.verbatim import OWN, english_status

MARKER = re.compile(r"<!--hadith\s+([^>]*?)-->(.*?)<!--/hadith-->", re.S)
# Below this much of the matn in the entry it could be a different report, so it stays
# a fallback; verify still flags anything short of an exact span as a variant.
MIN_CONTAINMENT = 0.85


def recheck(text, index):
    """(new_text, [change, ...]) for one chunk."""
    changes = []

    def _upgrade(m):
        attrs_raw, body = m.group(1), m.group(2)
        attrs = dict(re.findall(r"(\w+)=(\S+)", attrs_raw))
        if attrs.get("src") != "fallback" or not _arabic_of(body):
            return m.group(0)
        found = index.match(_arabic_of(body), min_conf=0.0, prefer=attrs.get("coll"))
        if found is None:
            return m.group(0)
        exact = _hadith_key(_arabic_of(body)) in _hadith_key(found["arabic"])
        if not exact and found["confidence"] < MIN_CONTAINMENT:
            return m.group(0)
        src = "arabic"
        if found["english"] and english_status(english_of(body), [found["english"]]) != OWN:
            src = "dataset"
        cite = attrs.get("num", "0")
        marker = "coll=%s num=%s cite=%s conf=%s src=%s" % (
            found["collection"], found["number"], cite, found["confidence"], src)
        changes.append({"was": "%s %s" % (attrs.get("coll"), cite),
                        "now": "%s %s" % (found["collection"], found["number"]),
                        "src": src, "exact": exact, "confidence": found["confidence"]})
        return "<!--hadith %s-->%s<!--/hadith-->" % (marker, body)

    return MARKER.sub(_upgrade, text), changes


def main():
    ap = argparse.ArgumentParser(description="see module docstring")
    ap.add_argument("run")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    index = HadithIndex.load()
    all_changes = []
    for path in sorted(glob.glob(os.path.join(args.run, "work", "translated", "chunk_*.md"))):
        with open(path, encoding="utf-8") as f:
            text = f.read()
        new_text, changes = recheck(text, index)
        all_changes += changes
        if changes and args.write:
            with open(path, "w", encoding="utf-8") as f:
                f.write(new_text)
    print(json.dumps({"run": args.run, "upgraded": len(all_changes), "written": args.write,
                      "changes": all_changes}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
