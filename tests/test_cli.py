import json
import os
import subprocess
import sys


def _run(mod, arabic, data_dir, *extra):
    env = dict(os.environ, RETRIEVAL_DATA_DIR=str(data_dir), PYTHONPATH=os.getcwd())
    out = subprocess.check_output(
        [sys.executable, "-m", mod, "--match", arabic] + list(extra), env=env)
    return json.loads(out)


def _write_hadith(tmp_path, collection, number, arabic, english="x"):
    hd = tmp_path / "hadith"
    hd.mkdir(exist_ok=True)
    (hd / ("ara-%s.json" % collection)).write_text(
        json.dumps({"hadiths": [{"hadithnumber": number, "text": arabic,
                                 "reference": {}}]}, ensure_ascii=False), encoding="utf-8")
    (hd / ("eng-%s.json" % collection)).write_text(
        json.dumps({"hadiths": [{"hadithnumber": number, "text": english}]},
                   ensure_ascii=False), encoding="utf-8")


def test_quran_cli(tmp_path):
    qd = tmp_path / "quran"
    qd.mkdir()

    def w(name, text):
        (qd / name).write_text(
            json.dumps({"quran": [{"chapter": 1, "verse": 1, "text": text}]}, ensure_ascii=False),
            encoding="utf-8")

    w("ara-quranuthmanihaf.json", "بحر نهر")
    w("eng-ummmuhammad.json", "sea river")
    w("eng-mustafakhattaba.json", "the sea")
    (tmp_path / "surah_names.json").write_text(
        json.dumps([{"number": 1, "arabic": "الفاتحة", "en": "Al-Fatihah"}], ensure_ascii=False),
        encoding="utf-8")
    r = _run("retrieval.quran_lookup", "بحر نهر", tmp_path)
    assert r["matched"] and r["ref_en"] == "[Al-Fatihah: 1]" and r["english_saheeh"] == "sea river"
    assert r["n_locations"] == 1 and not r["locations_truncated"]
    assert r["locations"] == [{"surah": 1, "ayah_start": 1, "ayah_end": 1,
                               "ref_en": "[Al-Fatihah: 1]"}]


def test_quran_cli_repeated_phrase_reports_all_locations(tmp_path):
    qd = tmp_path / "quran"
    qd.mkdir()
    verses = [{"chapter": 1, "verse": 1, "text": "بحر نهر"},
              {"chapter": 2, "verse": 9, "text": "بحر نهر"}]

    def w(name, key):
        (qd / name).write_text(json.dumps(
            {"quran": [dict(v, text=v["text"] if key == "ar" else "x") for v in verses]},
            ensure_ascii=False), encoding="utf-8")

    w("ara-quranuthmanihaf.json", "ar")
    w("eng-ummmuhammad.json", "en")
    w("eng-mustafakhattaba.json", "en")
    (tmp_path / "surah_names.json").write_text(
        json.dumps([{"number": 1, "arabic": "الفاتحة", "en": "Al-Fatihah"},
                    {"number": 2, "arabic": "البقرة", "en": "Al-Baqarah"}],
                   ensure_ascii=False), encoding="utf-8")
    r = _run("retrieval.quran_lookup", "بحر نهر", tmp_path)
    assert r["matched"] and r["surah"] == 1          # primary = first, as before
    assert r["n_locations"] == 2
    assert [loc["ref_en"] for loc in r["locations"]] == ["[Al-Fatihah: 1]", "[Al-Baqarah: 9]"]


def test_quran_cli_nearest_on_miss(tmp_path):
    qd = tmp_path / "quran"
    qd.mkdir()
    for name in ("ara-quranuthmanihaf.json", "eng-ummmuhammad.json", "eng-mustafakhattaba.json"):
        (qd / name).write_text(json.dumps(
            {"quran": [{"chapter": 1, "verse": 1, "text": "جبل شمس قمر نهر"}]},
            ensure_ascii=False), encoding="utf-8")
    r = _run("retrieval.quran_lookup", "جبل شمس قمر خطأ", tmp_path)
    assert r["matched"] is False
    assert r["nearest"][0]["surah"] == 1 and r["nearest"][0]["ayah"] == 1
    assert r["nearest"][0]["score"] >= 0.7 and "جبل" in r["nearest"][0]["arabic"]


def test_hadith_cli_no_match(tmp_path):
    (tmp_path / "hadith").mkdir()
    r = _run("retrieval.hadith_lookup", "لا شيء", tmp_path)
    assert r == {"matched": False}


def test_hadith_cli_match_includes_matched_true_and_alternates(tmp_path):
    _write_hadith(tmp_path, "bukhari", 13, "لا يؤمن احدكم حتى يحب لاخيه ما يحب لنفسه")
    r = _run("retrieval.hadith_lookup", "لا يؤمن احدكم حتى يحب لاخيه ما يحب لنفسه", tmp_path)
    assert r["matched"] is True and r["collection"] == "bukhari" and r["alternates"] == []


def test_hadith_cli_prefer_flag(tmp_path):
    matn = "لا يؤمن احدكم حتى يحب لاخيه ما يحب لنفسه"
    _write_hadith(tmp_path, "bukhari", 13, matn)
    _write_hadith(tmp_path, "nawawi", 13, matn)
    r = _run("retrieval.hadith_lookup", matn, tmp_path, "--prefer", "nawawi")
    assert r["collection"] == "nawawi"


def test_hadith_cli_nearest_on_sub_threshold(tmp_path):
    """A weak overlap must not dead-end: matched:false carries the best candidate so
    the subagent can correct its reading instead of burning retries."""
    _write_hadith(tmp_path, "muslim", 55, "الدين النصيحة لله ولكتابه ولرسوله")
    r = _run("retrieval.hadith_lookup", "الدين النصيحة زيتون تين رمان عنب", tmp_path)
    assert r["matched"] is False
    assert r["nearest"]["collection"] == "muslim" and r["nearest"]["number"] == 55
    assert 0 < r["nearest"]["confidence"] < 0.6 and "الدين" in r["nearest"]["arabic"]
