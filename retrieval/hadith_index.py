"""Inverted-index hadith matching by normalized Arabic matn (never by number)."""
import json
import os

from .cache import load_cached
from .normalize import normalize_arabic

COLLECTIONS = ["bukhari", "muslim", "abudawud", "tirmidhi", "nasai",
               "ibnmajah", "malik", "nawawi", "qudsi", "dehlawi"]
# Tie-break order for equal-quality matches: the Six Books + Muwatta before the
# derivative "forty" collections (nawawi/qudsi/dehlawi restate canonical hadith
# matn-only, which the recall term would otherwise always favor).
_CANONICAL_RANK = {c: i for i, c in enumerate(COLLECTIONS)}
# Candidates within this containment distance of the best are "ties": the query
# matches them all; only then do prefer/canonicity/recall arbitrate.
_EPS = 0.02


def _data_dir():
    return os.environ.get("RETRIEVAL_DATA_DIR",
                          os.path.join(os.path.dirname(__file__), "..", "data"))


def _load_english_fixes(path):
    """{(collection, number-as-str): [fix, ...]} from english-fixes.json (absent = {})."""
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    fixes = {}
    for fix in data.get("fixes", []):
        fixes.setdefault((fix["collection"], str(fix["number"])), []).append(fix)
    return fixes


def _apply_english_fixes(fixes, collection, number, english):
    import sys
    for fix in fixes.get((collection, str(number)), []):
        if fix["old"] in english:
            english = english.replace(fix["old"], fix["new"])
        else:
            print("english-fix %s %s: old text not found (dataset drift?): %r"
                  % (collection, number, fix["old"]), file=sys.stderr)
    return english


class HadithIndex:
    def __init__(self, entries):
        self.entries = entries                       # each has a precomputed "words" set
        self.inverted = {}
        for i, e in enumerate(entries):
            for w in e["words"]:
                self.inverted.setdefault(w, []).append(i)

    @classmethod
    def from_records(cls, records):
        entries = []
        for r in records:
            words = set(normalize_arabic(r["arabic"]).split())
            if not words:
                continue
            entries.append(dict(r, words=words))
        return cls(entries)

    @classmethod
    def load(cls, data_dir=None, collections=None):
        d = data_dir or os.path.join(_data_dir(), "hadith")
        colls = collections or COLLECTIONS
        # Sign-off-gated corrections to the datasets' English (OCR damage, typos) live
        # beside the dataset dirs; entries are added only after the user approves them.
        fixes_path = os.path.abspath(os.path.join(d, os.pardir, "english-fixes.json"))
        sources = [os.path.join(d, "%s-%s.json" % (pfx, c))
                   for c in colls for pfx in ("ara", "eng")] + [fixes_path]

        def build():
            fixes = _load_english_fixes(fixes_path)
            records = []
            for c in colls:
                ap, ep = os.path.join(d, "ara-%s.json" % c), os.path.join(d, "eng-%s.json" % c)
                if not os.path.exists(ap):
                    continue
                with open(ap, encoding="utf-8") as f:
                    ara = {h["hadithnumber"]: h for h in json.load(f)["hadiths"]}
                eng = {}
                if os.path.exists(ep):
                    with open(ep, encoding="utf-8") as f:
                        eng = {h["hadithnumber"]: h for h in json.load(f)["hadiths"]}
                for num, h in ara.items():
                    english = _apply_english_fixes(
                        fixes, c, num, eng.get(num, {}).get("text", ""))
                    records.append({"collection": c, "number": num, "arabic": h["text"],
                                    "english": english,
                                    "reference": h.get("reference", {})})
            return cls.from_records(records).entries

        # Cache the normalized entries (JSON parse + 40k matn normalizations dominate);
        # the inverted index is rebuilt from them at each load, which is cheap.
        entries = load_cached("hadith_index", sources, build, os.path.join(d, ".cache"))
        return cls(entries)

    def get(self, collection, number):
        """Exact (collection, number) lookup — used by out.verify body checks."""
        for e in self.entries:
            if e["collection"] == collection and str(e["number"]) == str(number):
                return e
        return None

    def match(self, arabic_query, min_conf=0.6, prefer=None, max_candidates=200):
        """Best dataset entry for an Arabic matn, or None below min_conf.

        Ranking: containment (fraction of the query found in the entry) decides;
        candidates within _EPS of the best are ties, ordered by the author's cited
        collection (`prefer`) first, then canonical rank, then recall. The result
        carries `alternates`: the other tied collections, so a caller can line the
        match up against the author's takhrij."""
        qwords = set(normalize_arabic(arabic_query).split())
        if not qwords:
            return None
        shared = {}
        for w in qwords:
            for i in self.inverted.get(w, []):
                shared[i] = shared.get(i, 0) + 1
        if not shared:
            return None
        ranked = sorted(shared, key=shared.get, reverse=True)[:max_candidates]
        scored = []                                  # (containment, recall, entry)
        for i in ranked:
            e = self.entries[i]
            inter = len(qwords & e["words"])
            scored.append((inter / len(qwords), inter / len(e["words"]), e))
        best_containment = max(s[0] for s in scored)
        if best_containment < min_conf:
            return None

        def order(s):
            containment, recall, e = s
            return (e["collection"] != prefer,
                    _CANONICAL_RANK.get(e["collection"], len(COLLECTIONS)),
                    -recall, -containment)

        shortlist = sorted((s for s in scored if s[0] >= best_containment - _EPS),
                           key=order)
        containment, _, e = shortlist[0]
        alternates, seen = [], {e["collection"]}
        for c2, _, e2 in shortlist[1:]:
            if e2["collection"] in seen:
                continue
            seen.add(e2["collection"])
            alternates.append({"collection": e2["collection"], "number": e2["number"],
                               "confidence": round(c2, 3)})
            if len(alternates) == 3:
                break
        return {"collection": e["collection"], "number": e["number"],
                "confidence": round(containment, 3), "arabic": e["arabic"],
                "english": e["english"], "reference": e["reference"],
                "alternates": alternates}
