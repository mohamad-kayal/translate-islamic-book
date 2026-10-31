"""Verify sacred-content markers in an assembled book or post.

Checks marker attributes (refs valid, collections known, review flags) AND — when
retrieval indexes are supplied — that the Arabic of every quran/hadith block is verbatim
dataset text and that its English is the dataset's too. A Qur'an block that fails is a
problem. A hadith block whose English is not the dataset's is not: the author may quote a
variant the published translation does not cover, so it is counted, flagged and marked †
at assembly. Each hadith therefore gets one of three statuses, from the check itself:

    verified     Arabic and English are both dataset text
    arabic_only  Arabic is dataset text; the English is this edition's own rendering
    unverified   not in the datasets at all; Arabic as printed, English our own
"""
import re

from retrieval.normalize import normalize_arabic
from retrieval.verbatim import OWN, english_status

_QURAN = re.compile(r"<!--quran\s+([^>]*?)-->(.*?)<!--/quran-->", re.S)
_HADITH = re.compile(r"<!--hadith\s+([^>]*?)-->(.*?)<!--/hadith-->", re.S)
_ANY_MARKER = re.compile(r"<!--(/?)(quran|hadith)[\s>-]")
_BRACKETED = re.compile(r"\[[^\]]*\]")   # [Maryam: 41] refs — Arabic surah name inside
_LATIN = re.compile(r"[A-Za-z]")
_CITATION_TAIL = re.compile(r"\s*\((?:[^()]|\([^()]*\))*\)\s*\.?\s*$")
_REF_TAIL = re.compile(r"\s*\[[^\]]*\]\s*$")
_COLLECTIONS = {"bukhari", "muslim", "abudawud", "tirmidhi", "nasai",
                "ibnmajah", "malik", "nawawi", "qudsi", "dehlawi",
                "ahmad", "hakim", "bayhaqi", "darimi", "tabarani"}
MIN_CONF = 0.6
VERIFIED, ARABIC_ONLY, UNVERIFIED = "verified", "arabic_only", "unverified"
OWN_RENDERING_MARK = "†"
# Below this fraction of matn words present in the dataset entry, a hadith body is a
# hard problem (wrong number / fabrication); above it but not an exact match, it is
# flagged for review (transmission variant or transcription difference).
_HADITH_PROBLEM_BELOW = 0.6
# Honorific phrases the dataset spells out but a book prints as a ligature (ﷺ/ﷻ, which
# normalize already drops). Stripped from BOTH sides so the matn stays contiguous.
_HONORIFICS = sorted({normalize_arabic(p) for p in [
    "صلى الله عليه وسلم", "صلى الله عليه وآله وسلم", "عليه الصلاة والسلام",
    "عليه السلام", "عليهم السلام", "عليها السلام", "عليهما السلام",
    "عز وجل", "جل جلاله", "جل وعلا", "تبارك وتعالى", "سبحانه وتعالى",
    "سبحانه", "تعالى", "رضي الله عنه", "رضي الله عنها", "رضي الله عنهم",
    "رضي الله عنهما"]}, key=len, reverse=True)


def _hadith_key(text):
    """Matn-matching key: honorific phrases removed, then alef/hamza-insensitive (the
    same folding the Quran matcher uses) so isnad prefixes, ﷺ/ﷻ-vs-spelled honorifics,
    and orthographic variants (السماوات/السموات) don't defeat a contiguous match."""
    t = normalize_arabic(text)
    for h in _HONORIFICS:
        t = t.replace(h, " ")
    t = re.sub(r"\s+", " ", t).replace("ا", "").replace("ء", "")
    return re.sub(r"\s+", " ", t).strip()


def _attrs(s):
    return dict(re.findall(r"(\w+)=(\S+)", s))


def parse_markers(md):
    return {"quran": [_attrs(a) for a, _ in _QURAN.findall(md)],
            "hadith": [_attrs(a) for a, _ in _HADITH.findall(md)]}


def _check_balance(md, problems):
    """Openers and closers of each marker type must strictly alternate."""
    state = {"quran": False, "hadith": False}   # inside-block flag
    for closing, kind in _ANY_MARKER.findall(md):
        if closing:
            if not state[kind]:
                problems.append("unbalanced %s markers: closer without opener" % kind)
                return
            state[kind] = False
        else:
            if state[kind]:
                problems.append("unbalanced %s markers: unclosed block" % kind)
                return
            state[kind] = True
    for kind, open_ in state.items():
        if open_:
            problems.append("unbalanced %s markers: unclosed block at end" % kind)


def _arabic_of(body):
    """The block's Arabic: leading lines that contain no Latin (refs stripped)."""
    lines = [ln.strip() for ln in body.split("\n") if ln.strip()]
    arabic = []
    for ln in lines:
        ln = _BRACKETED.sub(" ", ln)
        if _LATIN.search(ln):
            break
        arabic.append(ln)
    return normalize_arabic(" ".join(arabic))


def _strip_footnotes(text):
    """Remove pandoc ^[…] footnotes, nested brackets included."""
    out, i = [], 0
    while True:
        j = text.find("^[", i)
        if j < 0:
            return "".join(out) + text[i:]
        out.append(text[i:j])
        depth, k = 1, j + 2
        while k < len(text) and depth:
            depth += {"[": 1, "]": -1}.get(text[k], 0)
            k += 1
        i = k


def english_of(body):
    """The English a reader sees: the block's Latin lines without the verse reference,
    the citation tail, footnotes or the † mark."""
    lines = [ln.strip() for ln in body.split("\n") if ln.strip()]
    english = [ln for ln in lines if _LATIN.search(_BRACKETED.sub(" ", ln))]
    text = _strip_footnotes(" ".join(english)).replace(OWN_RENDERING_MARK, "").strip()
    text = _REF_TAIL.sub("", text)
    text = _CITATION_TAIL.sub("", text)
    return text.strip(" \"“”'‘’^")


def hadith_status(attrs, body, hadith_index):
    """VERIFIED, ARABIC_ONLY or UNVERIFIED — from the datasets, not from the marker."""
    if attrs.get("src") == "fallback":
        return UNVERIFIED
    entry = hadith_index.get(attrs.get("coll", ""), attrs.get("num", ""))
    if entry is None:
        return UNVERIFIED
    published = entry.get("english", "")
    if published and english_status(english_of(body), [published]) != OWN:
        return VERIFIED
    return ARABIC_ONLY


def _check_quran_body(attrs, body, quran_index, ref, problems):
    try:
        s = int(attrs.get("s", "0"))
        a0, a1 = (int(x) for x in attrs.get("a", "0-0").split("-"))
    except ValueError:
        return   # already reported as malformed
    verses = [quran_index.get_verse(s, a) for a in range(a0, a1 + 1)]
    if any(v is None for v in verses):
        problems.append("quran %s: verse(s) not found in dataset" % ref)
        return
    expected = normalize_arabic(" ".join(v["arabic"] for v in verses))
    got = _arabic_of(body)
    if not got:
        problems.append("quran %s: block has no Arabic body" % ref)
    elif not (got == expected or got in expected):   # verbatim, whole or a substring of the ayah
        problems.append("quran %s: Arabic body deviates from dataset text" % ref)
    published = " ".join(v.get(attrs.get("tr", "saheeh"), "") for v in verses).strip()
    english = english_of(body)
    if published and english and english_status(english, [published]) == OWN:
        problems.append("quran %s: English deviates from the %s text"
                        % (ref, attrs.get("tr", "saheeh")))


def _check_hadith_body(attrs, body, hadith_index, ref, problems, flagged):
    entry = hadith_index.get(attrs.get("coll", ""), attrs.get("num", ""))
    if entry is None:
        problems.append("hadith %s: not found in dataset (but src=dataset)" % ref)
        return
    got = _arabic_of(body)
    if not got:
        problems.append("hadith %s: block has no Arabic body" % ref)
        return
    if _hadith_key(got) in _hadith_key(entry["arabic"]):
        return   # matn is a verbatim (honorific/orthography-tolerant) span of the entry
    # Not an exact span: measure how much of the matn is in the entry to tell a
    # transmission/transcription variant (flag) from a wrong hadith (problem).
    matn = set(normalize_arabic(got).split())
    entry_words = set(normalize_arabic(entry["arabic"]).split())
    containment = len(matn & entry_words) / len(matn) if matn else 0.0
    if containment >= _HADITH_PROBLEM_BELOW:
        flagged.append("hadith %s: matn ~%.0f%% matches the dataset but not verbatim "
                       "(transmission variant or transcription — review)"
                       % (ref, containment * 100))
    else:
        problems.append("hadith %s: Arabic body deviates from dataset text "
                        "(only %.0f%% of matn words matched)" % (ref, containment * 100))


def verify(md, quran_index=None, hadith_index=None):
    problems, flagged = [], []
    _check_balance(md, problems)
    quran_blocks = _QURAN.findall(md)
    hadith_blocks = _HADITH.findall(md)
    sources = {VERIFIED: 0, ARABIC_ONLY: 0, UNVERIFIED: 0}

    for raw, body in quran_blocks:
        q = _attrs(raw)
        if "�" in body:
            flagged.append("quran %s: U+FFFD replacement character in block body "
                           "(damaged dataset English?) — review" % q.get("s", "?"))
        if q.get("tr") == "fallback" or q.get("s") == "0":
            flagged.append("quran fallback block (unmatched verse) — review")
            continue
        try:
            s = int(q.get("s", "0"))
            a0, a1 = (int(x) for x in q.get("a", "0-0").split("-"))
        except ValueError:
            problems.append("malformed quran marker: %s" % q)
            continue
        ref = "%s:%s-%s" % (s, a0, a1)
        if not (1 <= s <= 114):
            problems.append("quran surah out of range: %s" % s)
            continue
        if not (1 <= a0 <= a1):
            problems.append("quran ayah range invalid: %s-%s (surah %s)" % (a0, a1, s))
            continue
        if quran_index is not None:
            _check_quran_body(q, body, quran_index, ref, problems)

    for raw, body in hadith_blocks:
        h = _attrs(raw)
        coll = h.get("coll", "")
        ref = "%s %s" % (coll, h.get("num", "?"))
        if "�" in body:
            flagged.append("hadith %s: U+FFFD replacement character in block body "
                           "(damaged dataset English?) — review" % ref)
        is_fallback = h.get("src") == "fallback"
        # A fallback is text not in the bundled datasets (e.g. al-Darimi, Ahmad); its
        # collection may be unbundled or a placeholder, so it is a review flag, not an
        # error. Only dataset-sourced hadith must name a known collection.
        if not is_fallback and coll not in _COLLECTIONS:
            problems.append("unknown hadith collection: %s" % coll)
        if is_fallback:
            flagged.append("hadith %s sourced by fallback — review" % ref)
        try:
            if float(h.get("conf", "1")) < MIN_CONF:
                flagged.append("hadith %s low confidence %s — review" % (ref, h.get("conf")))
        except ValueError:
            problems.append("malformed hadith conf: %s" % h.get("conf"))
        if hadith_index is not None:
            if h.get("src") in ("dataset", "arabic"):
                _check_hadith_body(h, body, hadith_index, ref, problems, flagged)
            status = hadith_status(h, body, hadith_index)
            sources[status] += 1
            if status == ARABIC_ONLY:
                flagged.append("hadith %s: English is this edition's own rendering, not the "
                               "dataset's — marked %s" % (ref, OWN_RENDERING_MARK))

    result = {"n_quran": len(quran_blocks), "n_hadith": len(hadith_blocks),
              "problems": problems, "flagged": flagged,
              "bodies_checked": quran_index is not None or hadith_index is not None}
    if hadith_index is not None:
        result["hadith_sources"] = sources
    return result


if __name__ == "__main__":
    import argparse
    import json
    import sys
    ap = argparse.ArgumentParser(description="Verify sacred-content markers (attrs + verbatim bodies).")
    ap.add_argument("path", nargs="?", help="markdown file (default: stdin)")
    ap.add_argument("--no-body-checks", action="store_true",
                    help="skip dataset comparison (attrs only)")
    args = ap.parse_args()
    text = open(args.path, encoding="utf-8").read() if args.path else sys.stdin.read()
    qi = hi = None
    if not args.no_body_checks:
        from retrieval.hadith_index import HadithIndex
        from retrieval.quran_index import QuranIndex
        qi, hi = QuranIndex.load(), HadithIndex.load()
    print(json.dumps(verify(text, quran_index=qi, hadith_index=hi),
                     ensure_ascii=False, indent=2))
