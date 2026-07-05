"""Verify sacred-content markers in the assembled book: refs valid, collections known, flags."""
import re

_QURAN = re.compile(r"<!--quran\s+([^>]*?)-->", re.S)
_HADITH = re.compile(r"<!--hadith\s+([^>]*?)-->", re.S)
_COLLECTIONS = {"bukhari", "muslim", "abudawud", "tirmidhi", "nasai",
                "ibnmajah", "malik", "nawawi", "qudsi", "dehlawi",
                "ahmad", "hakim", "bayhaqi", "darimi", "tabarani"}
MIN_CONF = 0.6


def _attrs(s):
    return dict(re.findall(r"(\w+)=(\S+)", s))


def parse_markers(md):
    return {"quran": [_attrs(m) for m in _QURAN.findall(md)],
            "hadith": [_attrs(m) for m in _HADITH.findall(md)]}


def verify(md):
    m = parse_markers(md)
    problems, flagged = [], []
    for q in m["quran"]:
        try:
            s = int(q.get("s", "0"))
            a0, a1 = (int(x) for x in q.get("a", "0-0").split("-"))
        except ValueError:
            problems.append("malformed quran marker: %s" % q)
            continue
        if not (1 <= s <= 114):
            problems.append("quran surah out of range: %s" % s)
        if not (1 <= a0 <= a1):
            problems.append("quran ayah range invalid: %s-%s (surah %s)" % (a0, a1, s))
    for h in m["hadith"]:
        coll = h.get("coll", "")
        if coll not in _COLLECTIONS:
            problems.append("unknown hadith collection: %s" % coll)
        if h.get("src") == "fallback":
            flagged.append("hadith %s %s sourced by fallback — review" % (coll, h.get("num", "?")))
        try:
            if float(h.get("conf", "1")) < MIN_CONF:
                flagged.append("hadith %s %s low confidence %s — review"
                               % (coll, h.get("num", "?"), h.get("conf")))
        except ValueError:
            problems.append("malformed hadith conf: %s" % h.get("conf"))
    return {"n_quran": len(m["quran"]), "n_hadith": len(m["hadith"]),
            "problems": problems, "flagged": flagged}
