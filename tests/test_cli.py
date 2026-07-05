import json
import os
import subprocess
import sys


def _run(mod, arabic, data_dir):
    env = dict(os.environ, RETRIEVAL_DATA_DIR=str(data_dir), PYTHONPATH=os.getcwd())
    out = subprocess.check_output([sys.executable, "-m", mod, "--match", arabic], env=env)
    return json.loads(out)


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


def test_hadith_cli_no_match(tmp_path):
    (tmp_path / "hadith").mkdir()
    r = _run("retrieval.hadith_lookup", "لا شيء", tmp_path)
    assert r == {"matched": False}
