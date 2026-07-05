"""Load Quran editions; locate the ayah span covered by an Arabic quotation."""
import json
import os

from .normalize import normalize_arabic


def _data_dir():
    return os.environ.get("RETRIEVAL_DATA_DIR",
                          os.path.join(os.path.dirname(__file__), "..", "data"))


def _load_edition(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {(v["chapter"], v["verse"]): v["text"] for v in data["quran"]}


def _match_key(text):
    """Orthography-robust matching key: normalized text with every alef removed, so
    Uthmani spellings (dagger/superscript alef) and Imla'i spellings (full alef) of
    the same word collapse. Used only for locating verses; display text keeps alefs."""
    return normalize_arabic(text).replace("ا", "")


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
        for s in sorted(self._surah_text):
            pos = self._surah_text[s].find(qn)
            if pos == -1:
                continue
            end = pos + len(qn)
            overlaps = [a for (st, en, a) in self._surah_map[s] if st < end and en > pos]
            if overlaps:
                return (s, overlaps[0], overlaps[-1], 1.0)
        return None

    def get_verse(self, s, a):
        if (s, a) not in self.arabic:
            return None
        return {"surah": s, "ayah": a, "arabic": self.arabic[(s, a)],
                "saheeh": self.saheeh.get((s, a), ""), "clear": self.clear.get((s, a), "")}
