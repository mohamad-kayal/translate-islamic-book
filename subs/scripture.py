"""Scripture checks on translated lecture sentences.

A sentence typed quran/hadith with src "dataset" claims its English is the dataset's. When the
speaker's lead-in shares a segment with the quote, `quote` holds the verbatim part of `en`.
"""
import re

from retrieval.verbatim import OWN, english_status, words

_QURAN_REF = re.compile(r"(\d+):(\d+)(?:\s*[-–]\s*(\d+))?")
_HADITH_REF = re.compile(r"([a-z]+)\s+(\S+)")
_SEPARATOR = re.compile(r"[,;]")
_COLLECTION_ALIASES = (("ibn majah", "ibnmajah"), ("abu dawud", "abudawud"), ("abu dawood", "abudawud"))


def references(kind, ref, quran_index, hadith_index):
    """Every dataset English a sentence's ref points at ('3:164', 'bukhari 1, muslim 4927')."""
    out = []
    for part in _SEPARATOR.split(ref or ""):
        if kind == "quran":
            m = _QURAN_REF.search(part)
            if m:
                a0 = int(m.group(2))
                verses = [quran_index.get_verse(int(m.group(1)), a)
                          for a in range(a0, int(m.group(3) or a0) + 1)]
                if all(verses):
                    out += [" ".join(v[k] for v in verses) for k in ("saheeh", "clear")]
        else:
            text = part.strip().lower()
            for alias, collection in _COLLECTION_ALIASES:
                text = text.replace(alias, collection)
            m = _HADITH_REF.search(text)
            entry = hadith_index.get(m.group(1), m.group(2)) if m else None
            if entry is not None:
                out.append(entry["english"])
    return out


def sentence_problem(s, quran_index, hadith_index):
    """Why this sentence's scripture claim fails, or None."""
    if s.get("type") not in ("quran", "hadith") or s.get("src") != "dataset":
        return None
    en = (s.get("en") or "").replace("|", " ")
    quote = (s.get("quote") or "").replace("|", " ") or en
    if " %s " % " ".join(words(quote)) not in " %s " % " ".join(words(en)):
        return "quote is not part of en"
    refs = references(s["type"], s.get("ref"), quran_index, hadith_index)
    if not refs:
        return "ref %r not found in the datasets" % s.get("ref")
    if english_status(quote, refs) == OWN:
        return "English is not the dataset's wording (ref %s)" % s.get("ref")
    return None
