import json
from scripts import setup_data as sd


def test_edition_urls_are_commit_pinned():
    # upstream versions by a MOVING branch named "1" (no tags): a bare @1 would
    # track its tip, so URLs must pin an immutable commit SHA
    u = sd.edition_url("quran-api", "eng-ummmuhammad")
    assert "@%s/" % sd.API_REFS["quran-api"] in u and "@1/" not in u
    h = sd.edition_url("hadith-api", "ara-bukhari")
    assert "@%s/" % sd.API_REFS["hadith-api"] in h and "@1/" not in h
    assert all(len(ref) == 40 for ref in sd.API_REFS.values())   # full SHAs only


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


def _fake_data_dir(tmp_path):
    (tmp_path / "quran").mkdir()
    (tmp_path / "hadith").mkdir()
    (tmp_path / "quran" / "ara-quranuthmanihaf.json").write_bytes(b'{"quran": []}')
    (tmp_path / "hadith" / "ara-bukhari.json").write_bytes(b'{"hadiths": []}')
    return str(tmp_path)


def test_manifest_roundtrip_ok(tmp_path):
    d = _fake_data_dir(tmp_path)
    m = sd.write_manifest(d)
    assert set(m["files"]) == {"quran/ara-quranuthmanihaf.json", "hadith/ara-bukhari.json"}
    assert m["pins"] == sd.API_REFS
    assert sd.check_manifest(d) == []


def test_manifest_detects_tamper(tmp_path):
    d = _fake_data_dir(tmp_path)
    sd.write_manifest(d)
    (tmp_path / "quran" / "ara-quranuthmanihaf.json").write_bytes(b'{"quran": [1]}')
    problems = sd.check_manifest(d)
    assert any("mismatch" in p for p in problems)


def test_manifest_detects_missing_file(tmp_path):
    d = _fake_data_dir(tmp_path)
    sd.write_manifest(d)
    (tmp_path / "hadith" / "ara-bukhari.json").unlink()
    assert any("missing" in p for p in sd.check_manifest(d))


def test_check_without_manifest_reports(tmp_path):
    assert any("no manifest" in p for p in sd.check_manifest(str(tmp_path)))


def test_arabic_only_files_are_in_manifest_scope_and_commit_pinned():
    files = sd.dataset_files()
    assert "hadith/src-ahmad.csv" in files and "hadith/ara-ahmad.json" in files
    assert "/%s/" % sd.API_REFS["open-hadith-data"] in sd.open_hadith_url("x.csv")


def test_edition_from_csv_matches_the_hadith_api_shape():
    raw = '"1","\u200f \u200fحدثنا \u200f \u200fوكيع \u200f\n\u200fقال"\n"2","عن قيس"\n'
    edition = sd.edition_from_csv(raw.encode("utf-8-sig"))
    assert edition["hadiths"] == [
        {"hadithnumber": 1, "text": "حدثنا وكيع قال", "reference": {}},
        {"hadithnumber": 2, "text": "عن قيس", "reference": {}}]
