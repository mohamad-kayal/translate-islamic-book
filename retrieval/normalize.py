"""Arabic normalization: a diacritic-free, letter-unified form for robust matching."""
import re
import unicodedata

# Diacritic marks (harakat, tanwin, shadda, sukun, superscript alef, Quranic
# annotation signs) are stripped by Unicode category "Mn" in normalize_arabic below.
_TATWEEL = "ـ"
# KFGQPC "Hafs Smart" text separates a word's silent alef / alef-maqsura from its
# open-tanween mark (U+08F0-U+08F2) with a real space — a hack for the KFGQPC font
# that breaks joining in every standard font. The mark cluster may continue after
# the tanween (shadda in 19:44 عصيًّا, hamza-above in 2:48 شيئًا), so allow further
# Arabic combining marks before the space. A genuine next word never starts with a
# bare (unvoweled) alef in this encoding — verified over all 6236 ayat — so the
# rewrite has no false positives.
_KFGQPC_SILENT_SPACE = re.compile(
    "([\u08F0-\u08F2]"      # open fathatan / dammatan / kasratan
    "[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06DC\u06DF-\u06E4"
    "\u06E7\u06E8\u06EA-\u06ED\u08D3-\u08FF]*)"
    " (?=[\u0627\u0649])"   # space before bare alef / alef maqsura
)
# After unification, keep only Arabic base letters (hamza U+0621 .. ya U+064A) + space.
_NON_LETTER = re.compile("[^ء-ي ]")
_WS = re.compile(r"\s+")


def fix_kfgqpc_spaces(text):
    """Rejoin silent alef/alef-maqsura to its word (KFGQPC open-tanween space hack)."""
    if not text:
        return text
    return _KFGQPC_SILENT_SPACE.sub(r"\1", text)


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
