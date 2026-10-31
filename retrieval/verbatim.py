"""How closely a quoted English passage follows its dataset text.

The Arabic check proves the right passage was quoted; this one proves the English a reader
sees is the published wording and not something a model wrote. Case, punctuation, verse
numbers and inserted honorifics are ignored, because books add ﷺ where the dataset spells it
out or omits it. Word order and word choice are not.
"""
import difflib
import re

VERBATIM, STITCHED, OWN = "verbatim", "stitched", "own"
# Share of the quoted words that must appear, in order, for an elided or trimmed quotation
# to still count as the dataset's wording. Below this the words are mostly someone else's.
STITCHED_FROM = 0.95

_HONORIFIC = re.compile(
    r"\((?:peace|may allah|pbuh|saw|s\.a\.w|as|ra|ﷺ|alayhi|radi|sallallahu)[^()]*\)"
    r"|ﷺ"
    r"|\bpeace and blessings of allah be upon him\b"
    r"|\bpeace be upon him\b"
    r"|\bmay allah be pleased with (?:him|her|them(?: both)?)\b"
    r"|\bmay allah(?:'s)? (?:peace and )?blessings? be upon him\b"
    r"|\bmay allah bless him and grant him peace\b")
_VERSE_NUMBER = re.compile(r"\(\d+\)")
_APOSTROPHE = re.compile(r"[`'’‘ʿʾ]")
_NOT_WORD = re.compile(r"[^a-z0-9 ]+")


def words(text):
    t = _APOSTROPHE.sub("", (text or "").lower())
    t = _VERSE_NUMBER.sub(" ", _HONORIFIC.sub(" ", t))
    return _NOT_WORD.sub(" ", t).split()


def _in_order_share(quoted, reference):
    blocks = difflib.SequenceMatcher(None, quoted, reference, autojunk=False).get_matching_blocks()
    return sum(b.size for b in blocks) / len(quoted)


def english_status(quoted, references):
    """VERBATIM: one unbroken run of a reference. STITCHED: a trimmed or elided quotation,
    STITCHED_FROM of its words in order. OWN: anything else, including no reference."""
    q = words(quoted)
    if not q:
        return OWN
    refs = [words(r) for r in references if r]
    if any(" %s " % " ".join(q) in " %s " % " ".join(r) for r in refs):
        return VERBATIM
    if refs and max(_in_order_share(q, r) for r in refs) >= STITCHED_FROM:
        return STITCHED
    return OWN
