"""Reference + citation formatting matching the user's Al-Minhaj conventions."""
import json
import os

_SURAHS = None
_ARABIC_DIGITS = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")

# Transliterated collection names as used in the user's translation.
_COLL_EN = {
    "bukhari": "Al-Bukhari", "muslim": "Muslim", "abudawud": "Abu Dawood",
    "tirmidhi": "At-Tirmidhi", "nasai": "An-Nasa'i", "ibnmajah": "Ibn Majah",
    "malik": "Malik", "nawawi": "An-Nawawi", "qudsi": "Hadith Qudsi", "dehlawi": "Dehlawi",
}


def _data_dir():
    # Read the env at call time so in-process overrides (e.g. tests) take effect.
    return os.environ.get("RETRIEVAL_DATA_DIR",
                          os.path.join(os.path.dirname(__file__), "..", "data"))


def _surahs():
    global _SURAHS
    if _SURAHS is None:
        with open(os.path.join(_data_dir(), "surah_names.json"), encoding="utf-8") as f:
            _SURAHS = {s["number"]: s for s in json.load(f)}
    return _SURAHS


def surah_name_en(n):
    return _surahs()[n]["en"]


def surah_name_ar(n):
    return _surahs()[n]["arabic"]


def to_arabic_digits(n):
    return str(n).translate(_ARABIC_DIGITS)


def format_quran_ref_en(surah, a0, a1=None):
    rng = str(a0) if a1 is None or a1 == a0 else "%d-%d" % (a0, a1)
    return "[%s: %s]" % (surah_name_en(surah), rng)


def format_quran_ref_ar(surah, a0, a1=None):
    if a1 is None or a1 == a0:
        rng = to_arabic_digits(a0)
    else:
        rng = "%s-%s" % (to_arabic_digits(a0), to_arabic_digits(a1))
    return "[%s: %s]" % (surah_name_ar(surah), rng)


def format_hadith_citation(parts):
    """parts: [(collection, number), ...] -> '(Narrated by Al-Bukhari 79, and Muslim 2282)'."""
    segs = ["%s %s" % (_COLL_EN.get(c, c), n) for c, n in parts]
    body = segs[0] if len(segs) == 1 else ", ".join(segs[:-1]) + ", and " + segs[-1]
    return "(Narrated by %s)" % body
