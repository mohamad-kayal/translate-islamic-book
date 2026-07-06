"""Load Quran editions; locate the ayah span covered by an Arabic quotation."""
import json
import os
import re
import unicodedata

from .normalize import fix_kfgqpc_spaces, normalize_arabic

# Invisible bidi controls that leak from the dataset into pasted text.
_BIDI_CONTROLS = re.compile("[‎‏]")


def _data_dir():
    return os.environ.get("RETRIEVAL_DATA_DIR",
                          os.path.join(os.path.dirname(__file__), "..", "data"))


def _clean_text(text):
    return fix_kfgqpc_spaces(_BIDI_CONTROLS.sub("", text))


def _load_edition(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {(v["chapter"], v["verse"]): _clean_text(v["text"]) for v in data["quran"]}


def _match_key(text):
    """Orthography-robust matching key. Collapses Uthmani vs Imla'i spellings:
    a silent waw carrying a bare dagger alef (الصلوٰة) reads as alef (الصلاة), then
    every alef and hamza is removed so dagger-alef words (هٰذا/هذا) and hamza-carrier
    variants (ءَامنوا/آمنوا) unify. Used only for LOCATING verses; display text is
    untouched."""
    t = unicodedata.normalize("NFC", text or "")
    # waw + dagger alef with no vowel in between = silent waw pronounced as alef
    t = t.replace("وٰ", "ا")
    t = normalize_arabic(t)
    # Uthmani joins the vocative (يَٰٓأَيُّهَا is one word; Imla'i writes يا أيها as
    # two) — join the standalone particle so token boundaries agree.
    t = re.sub(r"(?<!\S)يا (?=\S)", "يا", t)
    return t.replace("ا", "").replace("ء", "")


class QuranIndex:
    def __init__(self, arabic, saheeh, clear):
        self.arabic = arabic
        self.saheeh = saheeh
        self.clear = clear
        self.order = sorted(arabic.keys())
        self.norm = {k: _match_key(v) for k, v in arabic.items()}
        # Per-surah match-key corpus + a char-offset -> ayah map, so a quotation can
        # be located even when it starts mid-ayah or spans several ayat.
        self._surah_text = {}
        self._surah_map = {}
        by_surah = {}
        for (s, a) in self.order:
            by_surah.setdefault(s, []).append(a)
        for s, ayat in by_surah.items():
            parts, spans, pos = [], [], 0
            for a in sorted(ayat):
                if pos > 0:
                    parts.append(" ")
                    pos += 1
                w = self.norm[(s, a)]
                spans.append((pos, pos + len(w), a))
                parts.append(w)
                pos += len(w)
            self._surah_text[s] = "".join(parts)
            self._surah_map[s] = spans

    @classmethod
    def load(cls, data_dir=None):
        d = data_dir or os.path.join(_data_dir(), "quran")
        return cls(
            _load_edition(os.path.join(d, "ara-quranuthmanihaf.json")),
            _load_edition(os.path.join(d, "eng-ummmuhammad.json")),
            _load_edition(os.path.join(d, "eng-mustafakhattaba.json")),
        )

    def identify_span(self, arabic_query):
        """Return (surah, ayah_start, ayah_end, coverage) or None.

        Locates the match-key query as a substring of a surah's match-key corpus,
        then maps the character range back to ayah number(s). Handles exact ayat,
        multi-ayah ranges, partial/mid-ayah quotes, and Uthmani-vs-Imla'i spelling.
        """
        qn = _match_key(arabic_query)
        if not qn:
            return None
        # Anchor at word boundaries: a quotation never starts or ends mid-word
        # (otherwise short queries match inside longer words, e.g. طه in مطهرة).
        pat = re.compile(r"(?<!\S)%s(?!\S)" % re.escape(qn))
        for s in sorted(self._surah_text):
            m = pat.search(self._surah_text[s])
            if m is None:
                continue
            pos, end = m.start(), m.end()
            overlaps = [a for (st, en, a) in self._surah_map[s] if st < end and en > pos]
            if overlaps:
                return (s, overlaps[0], overlaps[-1], 1.0)
        return None

    def get_verse(self, s, a):
        if (s, a) not in self.arabic:
            return None
        return {"surah": s, "ayah": a, "arabic": self.arabic[(s, a)],
                "saheeh": self.saheeh.get((s, a), ""), "clear": self.clear.get((s, a), "")}
