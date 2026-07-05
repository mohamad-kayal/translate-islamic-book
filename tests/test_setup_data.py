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
