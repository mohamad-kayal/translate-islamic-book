"""Load Quran editions; locate the ayah span covered by an Arabic quotation."""
import json
import os
import re
import unicodedata

from .cache import load_cached
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
        # Word -> ayat inverted index for nearest() suggestions on failed matches.
        self._word_ayat = {}
        for key, norm in self.norm.items():
            for w in set(norm.split()):
                self._word_ayat.setdefault(w, []).append(key)

    @classmethod
    def load(cls, data_dir=None):
        d = data_dir or os.path.join(_data_dir(), "quran")
        sources = [os.path.join(d, n + ".json") for n in
                   ("ara-quranuthmanihaf", "eng-ummmuhammad", "eng-mustafakhattaba")]

        def build():
            return tuple(_load_edition(p) for p in sources)

        # Cache the parsed editions; the match-key corpus is rebuilt at init (cheap).
        arabic, saheeh, clear = load_cached("quran_index", sources, build,
                                            os.path.join(d, ".cache"))
        return cls(arabic, saheeh, clear)

    def identify_spans(self, arabic_query, cap=20):
        """Every (surah, ayah_start, ayah_end) where the quotation occurs, in mushaf
        order (capped), plus the TRUE total count. A repeated (mutashabih) phrase —
        e.g. ولقد يسرنا القرآن للذكر at 54:17/22/32/40 — occurs at several locations
        the caller must disambiguate by the author's citation or the context;
        returning only the first would silently mis-cite.

        Locates the match-key query as a substring of each surah's match-key corpus,
        then maps character ranges back to ayah numbers. Handles exact ayat,
        multi-ayah ranges, partial/mid-ayah quotes, and Uthmani-vs-Imla'i spelling.
        """
        qn = _match_key(arabic_query)
        if not qn:
            return [], 0
        # Anchor at word boundaries: a quotation never starts or ends mid-word
        # (otherwise short queries match inside longer words, e.g. طه in مطهرة).
        pat = re.compile(r"(?<!\S)%s(?!\S)" % re.escape(qn))
        spans, total = [], 0
        for s in sorted(self._surah_text):
            for m in pat.finditer(self._surah_text[s]):
                pos, end = m.start(), m.end()
                overlaps = [a for (st, en, a) in self._surah_map[s]
                            if st < end and en > pos]
                if not overlaps:
                    continue
                total += 1
                if len(spans) < cap:
                    spans.append((s, overlaps[0], overlaps[-1]))
        return spans, total

    def identify_span(self, arabic_query):
        """First location as (surah, ayah_start, ayah_end, coverage) or None —
        the primary result; identify_spans carries the full location list."""
        spans, _ = self.identify_spans(arabic_query, cap=1)
        if not spans:
            return None
        s, a0, a1 = spans[0]
        return (s, a0, a1, 1.0)

    def nearest(self, arabic_query, k=3, min_score=0.5):
        """Closest ayat by word overlap for a query with NO verbatim span — the
        usual cause is a misread word in the page image. [(surah, ayah, score)],
        best first, so the caller can correct its reading instead of retrying blind."""
        qtokens = set(_match_key(arabic_query).split())
        if not qtokens:
            return []
        shared = {}
        for w in qtokens:
            for key in self._word_ayat.get(w, ()):
                shared[key] = shared.get(key, 0) + 1
        scored = sorted(((n / len(qtokens), key) for key, n in shared.items()),
                        key=lambda t: (-t[0], t[1]))
        return [(s, a, round(score, 3)) for score, (s, a) in scored[:k]
                if score >= min_score]

    def get_verse(self, s, a):
        if (s, a) not in self.arabic:
            return None
        return {"surah": s, "ayah": a, "arabic": self.arabic[(s, a)],
                "saheeh": self.saheeh.get((s, a), ""), "clear": self.clear.get((s, a), "")}
