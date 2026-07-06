"""Inverted-index hadith matching by normalized Arabic matn (never by number)."""
import json
import os

from .normalize import normalize_arabic

COLLECTIONS = ["bukhari", "muslim", "abudawud", "tirmidhi", "nasai",
               "ibnmajah", "malik", "nawawi", "qudsi", "dehlawi"]


def _data_dir():
    return os.environ.get("RETRIEVAL_DATA_DIR",
                          os.path.join(os.path.dirname(__file__), "..", "data"))


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
        records = []
        for c in (collections or COLLECTIONS):
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
                records.append({"collection": c, "number": num, "arabic": h["text"],
                                "english": eng.get(num, {}).get("text", ""),
                                "reference": h.get("reference", {})})
        return cls.from_records(records)

    def get(self, collection, number):
        """Exact (collection, number) lookup — used by out.verify body checks."""
        for e in self.entries:
            if e["collection"] == collection and str(e["number"]) == str(number):
                return e
        return None

    def match(self, arabic_query, min_conf=0.6, max_candidates=200):
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
        best = None                                  # (containment, recall, entry)
        for i in ranked:
            e = self.entries[i]
            inter = len(qwords & e["words"])
            containment = inter / len(qwords)         # fraction of query found in this hadith
            recall = inter / len(e["words"])          # fraction of this hadith covered by query
            if best is None or (containment, recall) > (best[0], best[1]):
                best = (containment, recall, e)
        if best is None or best[0] < min_conf:
            return None
        containment, _, e = best
        return {"collection": e["collection"], "number": e["number"],
                "confidence": round(containment, 3), "arabic": e["arabic"],
                "english": e["english"], "reference": e["reference"]}
