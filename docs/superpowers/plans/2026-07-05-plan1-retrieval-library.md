# Sacred-Content Retrieval Library — Implementation Plan (Plan 1 of 3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone, unit-tested Python library that, given a span of Arabic text, deterministically identifies and returns the authoritative Quran verse(s) (Saheeh International + The Clear Quran) or hadith (Arabic + English + citation) — the accuracy core of the `translate-islamic-book` skill.

**Architecture:** Pure-stdlib Python package `retrieval/`. A setup script downloads pinned public-domain datasets (Quran + hadith) and surah metadata into `data/`. Matching is by **normalized Arabic text**, never by number: Quran via substring location in a per-surah corpus keyed by an orthography-folding form (handles partial, mid-ayah, multi-ayah quotes, and Uthmani-vs-Imlā'ī spelling), hadith via an inverted index + word-containment score. Lookups expose a Python API and a JSON CLI (the interface the translation subagents in Plan 3 call).

**Tech Stack:** Python 3.9+ (system has 3.9.6), **standard library only at runtime** (`urllib`, `json`, `re`, `unicodedata`, `argparse`). Dev/test: `pytest`. Data via `urllib` from jsDelivr (fawazahmed0) + quran.com API.

## Global Constraints

- Python **3.9+**; **no third-party runtime dependencies** (house rule — a few lines beat a dependency). `pytest` is a dev/test dependency only.
- All file I/O uses `encoding="utf-8"`. All Arabic compared only after `normalize_arabic`.
- **Sacred content is retrieved, never generated.** No function may synthesize or paraphrase verse/hadith text.
- **Hadith citation** comes from the author's takhrij (Plan 3); this library returns the dataset's `(collection, number)` for *verification only* — numbering schemes differ across sources (dataset Bukhari aligns with the user's citations; dataset Muslim does not).
- Data directory configurable via env `RETRIEVAL_DATA_DIR` (default: repo `./data`).
- **Pinned editions** — Quran: `ara-quranuthmanihaf` (Uthmani Hafs; matching folds orthography by removing alefs so Imlā'ī quotes also resolve), `eng-ummmuhammad` (**Saheeh International**), `eng-mustafakhattaba` (**The Clear Quran**, Allah edition). Hadith `ara-`/`eng-` for: `bukhari, muslim, abudawud, tirmidhi, nasai, ibnmajah, malik, nawawi, qudsi, dehlawi`.
- Data sources are public domain: fawazahmed0 quran-api@1 + hadith-api@1 (Unlicense); surah names from quran.com API v4.
- **Arabic literals in code/tests:** write base letters as visible Arabic, but always express **combining diacritic marks as `\uXXXX` escapes** — a literal combining-mark range is invisible and error-prone (e.g., a mistyped range can delete real letters).

## File Structure

```
translate-islamic-book/
  retrieval/
    __init__.py          # package exports: quran_lookup(), hadith_match()
    normalize.py         # normalize_arabic(), tokenize()
    refs.py              # surah names, Arabic-Indic digits, ref + citation formatting
    quran_index.py       # QuranIndex: load editions, identify_span (substring), get_verse
    quran_lookup.py      # lookup() high-level API + JSON CLI
    hadith_index.py      # HadithIndex: inverted-index build, match()
    hadith_lookup.py     # match() high-level API + JSON CLI
  scripts/
    __init__.py
    setup_data.py        # download datasets + surah_names.json -> data/
  data/                  # (gitignored) populated by setup_data.py
  tests/
    test_normalize.py
    test_setup_data.py
    test_refs.py
    test_quran_lookup.py
    test_hadith_lookup.py
    test_cli.py
    test_golden_alminhaj.py   # integration; skips if data/ not populated
  requirements-dev.txt
  pytest.ini
```

---

### Task 1: Package scaffold + Arabic normalization

**Files:**
- Create: `translate-islamic-book/retrieval/__init__.py` (empty for now)
- Create: `translate-islamic-book/retrieval/normalize.py`
- Create: `translate-islamic-book/tests/test_normalize.py`
- Create: `translate-islamic-book/requirements-dev.txt`, `translate-islamic-book/pytest.ini`

**Interfaces:**
- Produces: `normalize_arabic(text: str) -> str` and `tokenize(text: str) -> list[str]`, consumed by every other module.

- [ ] **Step 1: Create dev tooling + venv**

`requirements-dev.txt`:
```
pytest>=7
```
`pytest.ini`:
```ini
[pytest]
testpaths = tests
python_files = test_*.py
markers =
    integration: requires populated data/ (deselect with -m "not integration")
```
Create empty `retrieval/__init__.py`, then:
```bash
cd translate-islamic-book && python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements-dev.txt
```

- [ ] **Step 2: Write the failing test** — `tests/test_normalize.py`

```python
from retrieval.normalize import normalize_arabic, tokenize

def test_strips_tashkeel():
    # مُحَمَّدٌ built from base letters + \u harakat must reduce to bare محمد
    voweled = "مُحَمَّدٌ"
    assert normalize_arabic(voweled) == "محمد"

def test_unifies_alef_variants():
    # إِنَّ ٱللَّه  (with hamza-below alef + wasla alef) == bare ان الله
    voweled = "إنَّ ٱلله"
    assert normalize_arabic(voweled) == normalize_arabic("ان الله") == "ان الله"

def test_unifies_alef_maqsura_and_ta_marbuta():
    assert normalize_arabic("على") == "علي"      # ى -> ي
    assert normalize_arabic("رحمة") == "رحمه"     # ة -> ه

def test_drops_symbols_digits_tatweel():
    # U+06DD end-of-ayah sign + Arabic-Indic digit ٢ + tatweel all vanish
    assert normalize_arabic("الحمد ۝٢ لله") == "الحمد لله"
    assert normalize_arabic("مــحمد") == "محمد"

def test_superscript_alef_removed():
    # هَٰذَا (with dagger alef U+0670) -> هذا
    assert normalize_arabic("هٰذا") == "هذا"

def test_empty_and_none_safe():
    assert normalize_arabic("") == ""
    assert normalize_arabic(None) == ""
    assert tokenize("بحر   نهر") == ["بحر", "نهر"]
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd translate-islamic-book && . .venv/bin/activate && python -m pytest tests/test_normalize.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'retrieval.normalize'`

- [ ] **Step 4: Write minimal implementation** — `retrieval/normalize.py`

```python
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
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_normalize.py -q`
Expected: PASS (6 passed)

- [ ] **Step 6: Commit**

```bash
git add retrieval/__init__.py retrieval/normalize.py tests/test_normalize.py requirements-dev.txt pytest.ini
git commit -m "feat(retrieval): Arabic normalization for matching"
```

---

### Task 2: Dataset + metadata setup script

**Files:**
- Create: `translate-islamic-book/scripts/setup_data.py`, `translate-islamic-book/scripts/__init__.py` (empty)
- Create: `translate-islamic-book/tests/test_setup_data.py`

**Interfaces:**
- Produces: `edition_url(api, name) -> str`, `chapters_url() -> str`, `download(url, dest, fetch=..., skip_existing=True) -> bool`, `build_surah_names(payload, dest)`, `main(argv=None)`. Download logic is tested via an injected `fetch` callable (no network in unit tests).
- On success `data/` holds `data/quran/<edition>.json` (4), `data/hadith/{ara,eng}-<coll>.json` (20), `data/surah_names.json`.

- [ ] **Step 1: Write the failing test** — `tests/test_setup_data.py`

```python
import json
from scripts import setup_data as sd

def test_edition_url_patterns():
    assert sd.edition_url("quran-api", "eng-ummmuhammad") == \
        "https://cdn.jsdelivr.net/gh/fawazahmed0/quran-api@1/editions/eng-ummmuhammad.json"
    assert sd.edition_url("hadith-api", "ara-bukhari") == \
        "https://cdn.jsdelivr.net/gh/fawazahmed0/hadith-api@1/editions/ara-bukhari.json"

def test_download_writes_and_skips_existing(tmp_path):
    calls = []
    def fake_fetch(url):
        calls.append(url)
        return b'{"ok": true}'
    dest = tmp_path / "sub" / "x.json"
    assert sd.download("http://u", str(dest), fetch=fake_fetch) is True
    assert json.loads(dest.read_text())["ok"] is True
    assert sd.download("http://u", str(dest), fetch=fake_fetch) is False   # skip
    assert len(calls) == 1

def test_build_surah_names_shape_and_sorted(tmp_path):
    payload = {"chapters": [
        {"id": 4, "name_simple": "An-Nisa", "name_arabic": "النساء"},
        {"id": 1, "name_simple": "Al-Fatihah", "name_arabic": "الفاتحة"},
    ]}
    out = tmp_path / "surah_names.json"
    sd.build_surah_names(payload, str(out))
    data = json.loads(out.read_text())
    assert {"number": 1, "arabic": "الفاتحة", "en": "Al-Fatihah"} in data
    assert [r["number"] for r in data] == [1, 4]   # sorted by number
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_setup_data.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.setup_data'`

- [ ] **Step 3: Write minimal implementation** — `scripts/setup_data.py` (and empty `scripts/__init__.py`)

```python
"""Download pinned public-domain Quran + hadith datasets and surah names into data/."""
import json
import os
import sys
import urllib.request

QURAN_EDITIONS = ["ara-quranuthmanihaf", "eng-ummmuhammad", "eng-mustafakhattaba"]
HADITH_COLLECTIONS = ["bukhari", "muslim", "abudawud", "tirmidhi", "nasai",
                      "ibnmajah", "malik", "nawawi", "qudsi", "dehlawi"]
_CDN = "https://cdn.jsdelivr.net/gh/fawazahmed0/{api}@1/editions/{name}.json"
_CHAPTERS = "https://api.quran.com/api/v4/chapters?language=en"

DATA_DIR = os.environ.get(
    "RETRIEVAL_DATA_DIR",
    os.path.join(os.path.dirname(__file__), "..", "data"),
)


def edition_url(api, name):
    return _CDN.format(api=api, name=name)


def chapters_url():
    return _CHAPTERS


def _http_fetch(url):
    with urllib.request.urlopen(url, timeout=60) as r:
        return r.read()


def download(url, dest, fetch=_http_fetch, skip_existing=True):
    """Fetch url -> dest. Returns True if downloaded, False if skipped."""
    if skip_existing and os.path.exists(dest) and os.path.getsize(dest) > 0:
        return False
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    data = fetch(url)
    with open(dest, "wb") as f:
        f.write(data)
    return True


def build_surah_names(chapters_payload, dest):
    rows = [{"number": c["id"], "arabic": c["name_arabic"], "en": c["name_simple"]}
            for c in chapters_payload["chapters"]]
    rows.sort(key=lambda r: r["number"])
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)


def main(argv=None):
    data = os.path.abspath(DATA_DIR)
    for name in QURAN_EDITIONS:
        d = download(edition_url("quran-api", name), os.path.join(data, "quran", name + ".json"))
        print(("downloaded " if d else "skipped    ") + name)
    for coll in HADITH_COLLECTIONS:
        for pfx in ("ara", "eng"):
            name = "%s-%s" % (pfx, coll)
            d = download(edition_url("hadith-api", name), os.path.join(data, "hadith", name + ".json"))
            print(("downloaded " if d else "skipped    ") + name)
    payload = json.loads(_http_fetch(chapters_url()).decode("utf-8"))
    build_surah_names(payload, os.path.join(data, "surah_names.json"))
    print("surah_names.json: %d surahs" % len(payload["chapters"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_setup_data.py -q`
Expected: PASS (3 passed)

- [ ] **Step 5: Populate real data (one-time, network) and sanity-check**

```bash
python scripts/setup_data.py
python -c "import json;print('ayat', len(json.load(open('data/quran/eng-ummmuhammad.json',encoding='utf-8'))['quran']))"
```
Expected: 23 download/skip lines (3 Quran + 20 hadith) + `surah_names.json: 114 surahs`, then `ayat 6236`.

- [ ] **Step 6: Commit**

```bash
git add scripts/setup_data.py scripts/__init__.py tests/test_setup_data.py
git commit -m "feat(setup): dataset + surah-names downloader (stdlib urllib, injectable fetch)"
```

---

### Task 3: Reference formatting (surah names, digits, citations)

**Files:**
- Create: `translate-islamic-book/retrieval/refs.py`
- Create: `translate-islamic-book/tests/test_refs.py`

**Interfaces:**
- Consumes: `data/surah_names.json` (Task 2) via `RETRIEVAL_DATA_DIR`.
- Produces: `surah_name_en(n)`, `surah_name_ar(n)`, `to_arabic_digits(n) -> str`, `format_quran_ref_en(surah, a0, a1=None) -> str`, `format_quran_ref_ar(surah, a0, a1=None) -> str`, `format_hadith_citation(parts: list[tuple[str,int]]) -> str`. Consumed by `quran_lookup` (Task 4) and Plan 3. Module-level cache `_SURAHS` (reset in tests).

- [ ] **Step 1: Write the failing test** — `tests/test_refs.py`

```python
import json
import pytest
from retrieval import refs

@pytest.fixture(autouse=True)
def _data(tmp_path, monkeypatch):
    names = [{"number": 4, "arabic": "النساء", "en": "An-Nisa"},
             {"number": 42, "arabic": "الشورى", "en": "Ash-Shuraa"}]
    (tmp_path / "surah_names.json").write_text(json.dumps(names, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("RETRIEVAL_DATA_DIR", str(tmp_path))
    refs._SURAHS = None   # reset cache

def test_surah_names():
    assert refs.surah_name_en(4) == "An-Nisa"
    assert refs.surah_name_ar(42) == "الشورى"

def test_arabic_digits():
    assert refs.to_arabic_digits(59) == "٥٩"   # ٥٩
    assert refs.to_arabic_digits(2) == "٢"          # ٢

def test_quran_ref_en_single_and_range():
    assert refs.format_quran_ref_en(4, 59) == "[An-Nisa: 59]"
    assert refs.format_quran_ref_en(42, 52, 53) == "[Ash-Shuraa: 52-53]"

def test_quran_ref_ar_uses_arabic_digits():
    assert refs.format_quran_ref_ar(4, 59) == "[النساء: ٥٩]"

def test_hadith_citation_one_two_three():
    assert refs.format_hadith_citation([("bukhari", 79)]) == "(Narrated by Al-Bukhari 79)"
    assert refs.format_hadith_citation([("bukhari", 79), ("muslim", 2282)]) == \
        "(Narrated by Al-Bukhari 79, and Muslim 2282)"
    assert refs.format_hadith_citation([("abudawud", 4605), ("tirmidhi", 2676), ("ibnmajah", 43)]) == \
        "(Narrated by Abu Dawood 4605, At-Tirmidhi 2676, and Ibn Majah 43)"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_refs.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'retrieval.refs'`

- [ ] **Step 3: Write minimal implementation** — `retrieval/refs.py`

```python
"""Reference + citation formatting matching the user's Al-Minhaj conventions."""
import json
import os

_DATA = os.environ.get("RETRIEVAL_DATA_DIR",
                       os.path.join(os.path.dirname(__file__), "..", "data"))
_SURAHS = None
_ARABIC_DIGITS = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")

# Transliterated collection names as used in the user's translation.
_COLL_EN = {
    "bukhari": "Al-Bukhari", "muslim": "Muslim", "abudawud": "Abu Dawood",
    "tirmidhi": "At-Tirmidhi", "nasai": "An-Nasa'i", "ibnmajah": "Ibn Majah",
    "malik": "Malik", "nawawi": "An-Nawawi", "qudsi": "Hadith Qudsi", "dehlawi": "Dehlawi",
}


def _surahs():
    global _SURAHS
    if _SURAHS is None:
        with open(os.path.join(_DATA, "surah_names.json"), encoding="utf-8") as f:
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_refs.py -q`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add retrieval/refs.py tests/test_refs.py
git commit -m "feat(retrieval): surah names, Arabic digits, ref + hadith citation formatting"
```

---

### Task 4: Quran index + high-level lookup

**Files:**
- Create: `translate-islamic-book/retrieval/quran_index.py`
- Create: `translate-islamic-book/retrieval/quran_lookup.py`
- Create: `translate-islamic-book/tests/test_quran_lookup.py`

**Interfaces:**
- Consumes: `retrieval.normalize`, `retrieval.refs`.
- Produces:
  - `QuranIndex(arabic: dict[(int,int),str], saheeh: dict, clear: dict)`, `QuranIndex.load(data_dir=None)`, `.identify_span(arabic_query) -> tuple(surah, ayah_start, ayah_end, coverage) | None`, `.get_verse(s, a) -> dict | None`.
  - `quran_lookup.lookup(arabic_query, translation="saheeh") -> dict` with keys `matched, surah, ayah_start, ayah_end, coverage, arabic, english_saheeh, english_clear, ref_en, ref_ar`.

- [ ] **Step 1: Write the failing test** — `tests/test_quran_lookup.py`

```python
from retrieval.quran_index import QuranIndex

# Synthetic 3-ayah surah (tashkeel-free base letters).
ARABIC = {(1, 1): "بحر نهر", (1, 2): "جبل شمس قمر", (1, 3): "ليل نهار"}
SAHEEH = {(1, 1): "sea river", (1, 2): "mountain sun moon", (1, 3): "night day"}
CLEAR  = {(1, 1): "the sea", (1, 2): "a mountain", (1, 3): "the night"}

def idx():
    return QuranIndex(ARABIC, SAHEEH, CLEAR)

def test_single_ayah_with_tashkeel_query():
    # query carries harakat (بَحْر نَهْر via \u marks) and must still match bare ayah 1
    q = "بَحر نَهر"
    assert idx().identify_span(q) == (1, 1, 1, 1.0)

def test_multi_ayah_range():
    assert idx().identify_span("جبل شمس قمر ليل نهار")[:3] == (1, 2, 3)

def test_partial_trailing_ayah():
    assert idx().identify_span("جبل شمس")[:3] == (1, 2, 2)

def test_midayah_quotation_resolves_to_containing_ayah():
    # 'قمر' is the LAST word of ayah 2 -> a partial/mid-ayah quote still resolves to ayah 2
    assert idx().identify_span("قمر")[:3] == (1, 2, 2)

def test_absent_text_returns_none():
    assert idx().identify_span("زيتون تين") is None

def test_alef_orthography_insensitive():
    # ayah stored with full alef (كتاب); a query missing that alef (Uthmani-style) still matches
    i2 = QuranIndex({(1, 1): "كتاب مبين"}, {(1, 1): "x"}, {(1, 1): "y"})
    assert i2.identify_span("كتب مبين")[:3] == (1, 1, 1)

def test_get_verse():
    assert idx().get_verse(1, 2)["saheeh"] == "mountain sun moon"
    assert idx().get_verse(9, 9) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_quran_lookup.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'retrieval.quran_index'`

- [ ] **Step 3: Write minimal implementation** — `retrieval/quran_index.py`

```python
"""Load Quran editions; locate the ayah span covered by an Arabic quotation."""
import json
import os

from .normalize import normalize_arabic

_DATA = os.environ.get("RETRIEVAL_DATA_DIR",
                       os.path.join(os.path.dirname(__file__), "..", "data"))


def _load_edition(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {(v["chapter"], v["verse"]): v["text"] for v in data["quran"]}


def _match_key(text):
    """Orthography-robust matching key: normalized text with every alef removed, so
    Uthmani spellings (dagger/superscript alef, e.g. the source Anwar al-Anbiya) and
    Imla'i spellings (full alef, e.g. Al-Minhaj) of the same word collapse to one
    form. Used only for locating verses; display text keeps its original alefs."""
    return normalize_arabic(text).replace("ا", "")


class QuranIndex:
    def __init__(self, arabic, saheeh, clear):
        self.arabic = arabic
        self.saheeh = saheeh
        self.clear = clear
        self.order = sorted(arabic.keys())
        self.norm = {k: _match_key(v) for k, v in arabic.items()}
        # Per-surah match-key corpus + a char-offset -> ayah map, so a quotation
        # can be located even when it starts mid-ayah or spans several ayat.
        self._surah_text = {}   # surah -> match-key text of the whole surah
        self._surah_map = {}    # surah -> list of (char_start, char_end, ayah)
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
        d = data_dir or os.path.join(_DATA, "quran")
        return cls(
            _load_edition(os.path.join(d, "ara-quranuthmanihaf.json")),
            _load_edition(os.path.join(d, "eng-ummmuhammad.json")),
            _load_edition(os.path.join(d, "eng-mustafakhattaba.json")),
        )

    def identify_span(self, arabic_query):
        """Return (surah, ayah_start, ayah_end, coverage) or None.

        Locates the match-key query as a substring of a surah's match-key text,
        then maps the matched character range back to ayah number(s). Handles exact
        ayah, multi-ayah ranges, partial/mid-ayah quotations, and Uthmani-vs-Imla'i
        spelling differences (via _match_key). coverage is 1.0 for a substring hit;
        no hit -> None (the caller flags it for the fallback path).
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
```

- [ ] **Step 4: Write `retrieval/quran_lookup.py`**

```python
"""High-level Quran retrieval + JSON CLI (called by translation subagents)."""
import argparse
import json

from .quran_index import QuranIndex
from .refs import format_quran_ref_ar, format_quran_ref_en

_INDEX = None


def _index():
    global _INDEX
    if _INDEX is None:
        _INDEX = QuranIndex.load()
    return _INDEX


def lookup(arabic_query, translation="saheeh"):
    idx = _index()
    span = idx.identify_span(arabic_query)
    if span is None:
        return {"matched": False}
    s, a0, a1, cov = span
    verses = [idx.get_verse(s, a) for a in range(a0, a1 + 1)]
    return {
        "matched": True,
        "surah": s, "ayah_start": a0, "ayah_end": a1, "coverage": cov,
        "arabic": " ".join(v["arabic"] for v in verses),
        "english_saheeh": " ".join(v["saheeh"] for v in verses),
        "english_clear": " ".join(v["clear"] for v in verses),
        "ref_en": format_quran_ref_en(s, a0, a1),
        "ref_ar": format_quran_ref_ar(s, a0, a1),
    }


def main(argv=None):
    p = argparse.ArgumentParser(description="Identify + retrieve Quran verse(s) from Arabic.")
    p.add_argument("--match", required=True, help="Arabic quotation to identify")
    args = p.parse_args(argv)
    print(json.dumps(lookup(args.match), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_quran_lookup.py -q`
Expected: PASS (7 passed)

- [ ] **Step 6: Commit**

```bash
git add retrieval/quran_index.py retrieval/quran_lookup.py tests/test_quran_lookup.py
git commit -m "feat(retrieval): Quran ayah-span identification (substring) + verse retrieval"
```

---

### Task 5: Hadith index + fuzzy matching

**Files:**
- Create: `translate-islamic-book/retrieval/hadith_index.py`
- Create: `translate-islamic-book/retrieval/hadith_lookup.py`
- Create: `translate-islamic-book/tests/test_hadith_lookup.py`

**Interfaces:**
- Consumes: `retrieval.normalize`.
- Produces:
  - `HadithIndex.from_records(records)` where each record is `{"collection","number","arabic","english","reference"}`; `HadithIndex.load(data_dir=None, collections=None)`; `.match(arabic_query, min_conf=0.6) -> dict | None` with keys `collection, number, confidence, arabic, english, reference`.
  - `hadith_lookup.match(arabic_query, min_conf=0.6) -> dict` (`{"matched": False}` when below threshold).

- [ ] **Step 1: Write the failing test** — `tests/test_hadith_lookup.py`

```python
from retrieval.hadith_index import HadithIndex

# Synthetic records; queries are word-subsets of a record so containment is decisive.
RECORDS = [
    {"collection": "bukhari", "number": 1,
     "arabic": "انما الاعمال بالنيات وانما لكل امرئ ما نوى",
     "english": "Actions are but by intention...", "reference": {"book": 1, "hadith": 1}},
    {"collection": "muslim", "number": 2408,
     "arabic": "كتاب الله هو حبل الله من اتبعه كان على الهدى ومن تركه كان على ضلالة",
     "english": "The Book of Allah is the rope of Allah...", "reference": {"book": 44, "hadith": 55}},
    {"collection": "bukhari", "number": 79,
     "arabic": "مثل ما بعثني الله به من الهدى والعلم كمثل الغيث الكثير اصاب ارضا",
     "english": "The example of guidance and knowledge...", "reference": {"book": 3, "hadith": 20}},
]

def idx():
    return HadithIndex.from_records(RECORDS)

def test_matches_full_matn():
    r = idx().match("انما الاعمال بالنيات وانما لكل امرئ ما نوى")
    assert r["collection"] == "bukhari" and r["number"] == 1 and r["confidence"] >= 0.9

def test_matches_by_content_not_number():
    r = idx().match("كتاب الله هو حبل الله من اتبعه كان على الهدى")
    assert r["collection"] == "muslim" and "rope" in r["english"]

def test_below_threshold_returns_none():
    assert idx().match("زيتون تين رمان عنب موز برتقال فراولة") is None

def test_empty_query_returns_none():
    assert idx().match("") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_hadith_lookup.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'retrieval.hadith_index'`

- [ ] **Step 3: Write minimal implementation** — `retrieval/hadith_index.py`

```python
"""Inverted-index hadith matching by normalized Arabic matn (never by number)."""
import json
import os

from .normalize import normalize_arabic

_DATA = os.environ.get("RETRIEVAL_DATA_DIR",
                       os.path.join(os.path.dirname(__file__), "..", "data"))
COLLECTIONS = ["bukhari", "muslim", "abudawud", "tirmidhi", "nasai",
               "ibnmajah", "malik", "nawawi", "qudsi", "dehlawi"]


class HadithIndex:
    def __init__(self, entries):
        self.entries = entries                       # each has a precomputed "words" set
        self.inverted = {}
        for i, e in enumerate(entries):
            for w in e["words"]:
                self.inverted.setdefault(w, []).append(i)

    @classmethod
    def from_records(cls, records):
        entries = []
        for r in records:
            words = set(normalize_arabic(r["arabic"]).split())
            if not words:
                continue
            entries.append(dict(r, words=words))
        return cls(entries)

    @classmethod
    def load(cls, data_dir=None, collections=None):
        d = data_dir or os.path.join(_DATA, "hadith")
        records = []
        for c in (collections or COLLECTIONS):
            ap, ep = os.path.join(d, "ara-%s.json" % c), os.path.join(d, "eng-%s.json" % c)
            if not os.path.exists(ap):
                continue
            with open(ap, encoding="utf-8") as f:
                ara = {h["hadithnumber"]: h for h in json.load(f)["hadiths"]}
            eng = {}
            if os.path.exists(ep):
                with open(ep, encoding="utf-8") as f:
                    eng = {h["hadithnumber"]: h for h in json.load(f)["hadiths"]}
            for num, h in ara.items():
                records.append({"collection": c, "number": num, "arabic": h["text"],
                                "english": eng.get(num, {}).get("text", ""),
                                "reference": h.get("reference", {})})
        return cls.from_records(records)

    def match(self, arabic_query, min_conf=0.6, max_candidates=200):
        qwords = set(normalize_arabic(arabic_query).split())
        if not qwords:
            return None
        shared = {}
        for w in qwords:
            for i in self.inverted.get(w, []):
                shared[i] = shared.get(i, 0) + 1
        if not shared:
            return None
        ranked = sorted(shared, key=shared.get, reverse=True)[:max_candidates]
        best = None                                  # (containment, recall, entry)
        for i in ranked:
            e = self.entries[i]
            inter = len(qwords & e["words"])
            containment = inter / len(qwords)         # fraction of query found in this hadith
            recall = inter / len(e["words"])          # fraction of this hadith covered by query
            if best is None or (containment, recall) > (best[0], best[1]):
                best = (containment, recall, e)
        if best is None or best[0] < min_conf:
            return None
        containment, _, e = best
        return {"collection": e["collection"], "number": e["number"],
                "confidence": round(containment, 3), "arabic": e["arabic"],
                "english": e["english"], "reference": e["reference"]}
```

- [ ] **Step 4: Write `retrieval/hadith_lookup.py`**

```python
"""High-level hadith retrieval + JSON CLI (called by translation subagents)."""
import argparse
import json

from .hadith_index import HadithIndex

_INDEX = None


def _index():
    global _INDEX
    if _INDEX is None:
        _INDEX = HadithIndex.load()
    return _INDEX


def match(arabic_query, min_conf=0.6):
    r = _index().match(arabic_query, min_conf=min_conf)
    return r if r is not None else {"matched": False}


def main(argv=None):
    p = argparse.ArgumentParser(description="Match an Arabic hadith matn to the dataset.")
    p.add_argument("--match", required=True)
    p.add_argument("--min-conf", type=float, default=0.6)
    args = p.parse_args(argv)
    print(json.dumps(match(args.match, args.min_conf), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_hadith_lookup.py -q`
Expected: PASS (4 passed)

- [ ] **Step 6: Commit**

```bash
git add retrieval/hadith_index.py retrieval/hadith_lookup.py tests/test_hadith_lookup.py
git commit -m "feat(retrieval): hadith matn matching via inverted index + containment score"
```

---

### Task 6: Package exports + CLI integration test

**Files:**
- Modify: `translate-islamic-book/retrieval/__init__.py`
- Create: `translate-islamic-book/tests/test_cli.py`

**Interfaces:**
- Produces: `from retrieval import quran_lookup, hadith_match`. CLI: `python -m retrieval.quran_lookup --match "<ar>"` and `python -m retrieval.hadith_lookup --match "<ar>"` print one JSON object to stdout.

- [ ] **Step 1: Write the failing test** — `tests/test_cli.py`

```python
import json, os, subprocess, sys

def _run(mod, arabic, data_dir):
    env = dict(os.environ, RETRIEVAL_DATA_DIR=str(data_dir), PYTHONPATH=os.getcwd())
    out = subprocess.check_output([sys.executable, "-m", mod, "--match", arabic], env=env)
    return json.loads(out)

def test_quran_cli(tmp_path):
    qd = tmp_path / "quran"; qd.mkdir()
    def w(name, text):
        (qd / name).write_text(json.dumps({"quran": [{"chapter": 1, "verse": 1, "text": text}]},
                                          ensure_ascii=False), encoding="utf-8")
    w("ara-quranuthmanihaf.json", "بحر نهر")
    w("eng-ummmuhammad.json", "sea river")
    w("eng-mustafakhattaba.json", "the sea")
    (tmp_path / "surah_names.json").write_text(
        json.dumps([{"number": 1, "arabic": "الفاتحة", "en": "Al-Fatihah"}], ensure_ascii=False),
        encoding="utf-8")
    r = _run("retrieval.quran_lookup", "بحر نهر", tmp_path)
    assert r["matched"] and r["ref_en"] == "[Al-Fatihah: 1]" and r["english_saheeh"] == "sea river"

def test_hadith_cli_no_match(tmp_path):
    (tmp_path / "hadith").mkdir()
    r = _run("retrieval.hadith_lookup", "لا شيء", tmp_path)
    assert r == {"matched": False}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_cli.py -q`
Expected: FAIL — `ImportError` on `from retrieval import quran_lookup, hadith_match`.

- [ ] **Step 3: Write minimal implementation** — `retrieval/__init__.py`

```python
"""Sacred-content retrieval: Quran + hadith lookup by normalized Arabic text."""
from .quran_lookup import lookup as quran_lookup      # noqa: F401
from .hadith_lookup import match as hadith_match       # noqa: F401

__all__ = ["quran_lookup", "hadith_match"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_cli.py -q`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add retrieval/__init__.py tests/test_cli.py
git commit -m "feat(retrieval): package exports + CLI integration coverage"
```

---

### Task 7: Golden benchmark against real Al-Minhaj data

**Files:**
- Create: `translate-islamic-book/tests/test_golden_alminhaj.py`

**Interfaces:**
- Consumes real `data/` (Task 2). Marked `integration`; skips cleanly if data absent so the unit suite stays offline. Uses real quotations exactly as they appear in the *Al-Minhaj* source.

- [ ] **Step 1: Write the test** — `tests/test_golden_alminhaj.py`

```python
import os
import pytest

pytestmark = pytest.mark.integration
DATA = os.environ.get("RETRIEVAL_DATA_DIR",
                      os.path.join(os.path.dirname(__file__), "..", "data"))

def _need(path):
    if not os.path.exists(path):
        pytest.skip("run scripts/setup_data.py first (%s missing)" % path)

def test_quran_annisa_59_partial_quote():
    # The source quotes only the second half of An-Nisa 59 -> mid-ayah match must work.
    _need(os.path.join(DATA, "quran", "eng-ummmuhammad.json"))
    from retrieval.quran_lookup import lookup
    r = lookup("فإن تنازعتم في شيء فردوه إلى الله والرسول")
    assert r["matched"] and r["surah"] == 4 and r["ayah_start"] == 59
    assert r["ref_en"] == "[An-Nisa: 59]"
    assert "refer it to Allah and the Messenger" in r["english_saheeh"]

def test_quran_multiayah_range_ashshura_52_53():
    _need(os.path.join(DATA, "quran", "ara-quranuthmanihaf.json"))
    from retrieval.quran_lookup import lookup
    r = lookup("وإنك لتهدي إلى صراط مستقيم صراط الله الذي له ما في السماوات وما في الأرض")
    assert r["matched"] and r["surah"] == 42
    assert (r["ayah_start"], r["ayah_end"]) == (52, 53)

def test_hadith_bukhari_79_rain_parable():
    _need(os.path.join(DATA, "hadith", "ara-bukhari.json"))
    from retrieval.hadith_lookup import match
    r = match("مثل ما بعثني الله به من الهدى والعلم كمثل الغيث الكثير أصاب أرضا")
    assert r.get("collection") == "bukhari" and r.get("number") == 79
    assert "guidance" in r["english"].lower()
```

- [ ] **Step 2: Run the integration test against real data**

Run: `python -m pytest tests/test_golden_alminhaj.py -q -m integration`
Expected: PASS (3 passed) when `data/` is populated; SKIPPED otherwise.
*If a golden Arabic string differs slightly from the dataset's orthography and fails to match, adjust the test quotation to the exact source text — the retrieval logic is what's under test, not the transcription.*

- [ ] **Step 3: Run the full unit suite (offline) to confirm nothing regressed**

Run: `python -m pytest -q -m "not integration"`
Expected: PASS, 0 failures.

- [ ] **Step 4: Commit**

```bash
git add tests/test_golden_alminhaj.py
git commit -m "test(retrieval): golden benchmark vs Al-Minhaj (An-Nisa 59, Ash-Shura 52-53, Bukhari 79)"
```

---

## Self-Review

**Spec coverage** (design §7, §8, §11):
- Bundled datasets + exact editions → Task 2. ✓
- Quran ayah-span retrieval incl. **partial/mid-ayah and ranges** → Task 4. ✓
- Hadith fuzzy matn matching + confidence + "never by number" → Task 5. ✓
- Below-threshold / absent → `{"matched": False}` / `None`, the signal Plan 3's fallback consumes. ✓
- Saheeh Intl + Clear Quran both carried in the payload (`english_saheeh` / `english_clear`) → Task 4. ✓ (which prints + Clear-Quran flagging = Plan 3.)
- Reference formatting both scripts + hadith citation style → Task 3. ✓
- Normalization (tashkeel/alef/maqsura/ta-marbuta/superscript-alef) → Task 1. ✓

**Deferred to Plan 3 (intentional, not gaps):** web/LLM fallback, author-takhrij citation reconciliation, diacritical "Allāh/Muḥammad" post-process, isnad-stripping for rare long-narration edge cases.

**Placeholder scan:** none — every step has runnable code + exact commands.

**Type consistency:** `identify_span -> (surah, ayah_start, ayah_end, coverage)` used consistently; `lookup()` keys (`english_saheeh`, `english_clear`, `ref_en`, `ref_ar`) match across Tasks 4/6/7; `match()` keys (`collection, number, confidence, arabic, english, reference`) match across Tasks 5/7; `RETRIEVAL_DATA_DIR` is the single data-dir contract everywhere. ✓

**Correctness notes — found and fixed by running the code against real data during review:**
(1) `identify_span` uses substring location, so partial/mid-ayah quotes (e.g. the source's half-quote of An-Nisa 59) resolve correctly — an earlier start-anchored version missed them.
(2) Diacritics are stripped by Unicode category `Mn`, not a hand-written codepoint range (which is invisible in source and easy to mis-bound).
(3) **Orthography folding:** the two target books differ — *Al-Minhaj* is Imlā'ī, *Anwar al-Anbiya* is Uthmani. A verse quoted in either spelling must match the dataset, so the match key removes alefs (`_match_key`), collapsing dagger-alef vs full-alef. Verified on real data: An-Nisa 59 (Imlā'ī mid-ayah quote), Ash-Shura 52-53 (range), and a Uthmani-orthography query all resolve; gibberish returns `None`; Bukhari 79 matn matches its full-isnad entry at confidence 1.0.
