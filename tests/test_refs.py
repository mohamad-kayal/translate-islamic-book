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
    assert refs.to_arabic_digits(59) == "٥٩"
    assert refs.to_arabic_digits(2) == "٢"


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
