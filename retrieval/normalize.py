"""Arabic normalization: a diacritic-free, letter-unified form for robust matching."""
import re
import unicodedata

# Diacritic marks (harakat, tanwin, shadda, sukun, superscript alef, Quranic
# annotation signs) are stripped by Unicode category "Mn" in normalize_arabic below.
_TATWEEL = "ـ"
# After unification, keep only Arabic base letters (hamza U+0621 .. ya U+064A) + space.
_NON_LETTER = re.compile("[^ء-ي ]")
_WS = re.compile(r"\s+")


def normalize_arabic(text):
    """Return a normalized form suitable for equality/containment matching."""
    if not text:
        return ""
    t = unicodedata.normalize("NFC", text)
    # Drop every Arabic combining mark (harakat, tanwin, shadda, sukun, superscript
    # alef, Quranic annotation signs) by Unicode category — no fragile codepoint range.
    t = "".join(ch for ch in t if unicodedata.category(ch) != "Mn")
    t = t.replace(_TATWEEL, "")
    t = re.sub("[آأإٱ]", "ا", t)   # آ أ إ ٱ -> ا
    t = t.replace("ى", "ي")                        # ى -> ي
    t = t.replace("ة", "ه")                        # ة -> ه
    t = t.replace("ؤ", "ء").replace("ئ", "ء")  # ؤ ئ -> ء
    t = _NON_LETTER.sub(" ", t)
    return _WS.sub(" ", t).strip()


def tokenize(text):
    """Whitespace tokens of the normalized text."""
    n = normalize_arabic(text)
    return n.split() if n else []
