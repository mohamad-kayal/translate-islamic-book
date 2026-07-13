import json
import os
import pickle

from retrieval.cache import load_cached


def _counter_build(value="payload"):
    """A build() that counts invocations."""
    calls = {"n": 0}

    def build():
        calls["n"] += 1
        return {"value": value, "call": calls["n"]}

    return build, calls


def _src(tmp_path, name="src.json", content="{}"):
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return str(p)


def test_second_load_hits_cache(tmp_path):
    src = _src(tmp_path)
    build, calls = _counter_build()
    a = load_cached("idx", [src], build, str(tmp_path / ".cache"))
    b = load_cached("idx", [src], build, str(tmp_path / ".cache"))
    assert calls["n"] == 1
    assert a == b


def test_source_change_invalidates(tmp_path):
    src = _src(tmp_path)
    build, calls = _counter_build()
    load_cached("idx", [src], build, str(tmp_path / ".cache"))
    with open(src, "w", encoding="utf-8") as f:
        json.dump({"changed": True}, f)   # size + mtime change
    load_cached("idx", [src], build, str(tmp_path / ".cache"))
    assert calls["n"] == 2


def test_corrupt_pickle_falls_back_to_build(tmp_path):
    src = _src(tmp_path)
    build, calls = _counter_build()
    cache_dir = str(tmp_path / ".cache")
    load_cached("idx", [src], build, cache_dir)
    with open(os.path.join(cache_dir, "idx.pkl"), "wb") as f:
        f.write(b"not a pickle")
    out = load_cached("idx", [src], build, cache_dir)
    assert calls["n"] == 2 and out["value"] == "payload"
    # and the rewritten cache works again
    load_cached("idx", [src], build, cache_dir)
    assert calls["n"] == 2


def test_env_kill_switch_bypasses_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("RETRIEVAL_NO_CACHE", "1")
    src = _src(tmp_path)
    build, calls = _counter_build()
    load_cached("idx", [src], build, str(tmp_path / ".cache"))
    load_cached("idx", [src], build, str(tmp_path / ".cache"))
    assert calls["n"] == 2
    assert not os.path.exists(str(tmp_path / ".cache" / "idx.pkl"))


def test_schema_bump_invalidates(tmp_path):
    src = _src(tmp_path)
    build, calls = _counter_build()
    load_cached("idx", [src], build, str(tmp_path / ".cache"), schema=1)
    load_cached("idx", [src], build, str(tmp_path / ".cache"), schema=2)
    assert calls["n"] == 2


def test_missing_optional_source_tolerated_and_appearance_invalidates(tmp_path):
    src = _src(tmp_path)
    optional = str(tmp_path / "english-fixes.json")   # does not exist yet
    build, calls = _counter_build()
    load_cached("idx", [src, optional], build, str(tmp_path / ".cache"))
    load_cached("idx", [src, optional], build, str(tmp_path / ".cache"))
    assert calls["n"] == 1                            # cached while still absent
    with open(optional, "w", encoding="utf-8") as f:
        f.write("{}")
    load_cached("idx", [src, optional], build, str(tmp_path / ".cache"))
    assert calls["n"] == 2                            # appearing later invalidates


def test_unwritable_cache_dir_fails_open(tmp_path):
    src = _src(tmp_path)
    build, calls = _counter_build()
    blocked = tmp_path / "blocked"
    blocked.write_text("a file, not a dir", encoding="utf-8")
    out = load_cached("idx", [src], build, str(blocked))
    assert calls["n"] == 1 and out["value"] == "payload"


def test_hadith_index_load_uses_cache(tmp_path):
    """Integration: HadithIndex.load caches; editing the dataset is seen (invalidation)."""
    from retrieval.hadith_index import HadithIndex
    d = tmp_path / "hadith"
    d.mkdir()
    def write(text):
        with open(d / "ara-bukhari.json", "w", encoding="utf-8") as f:
            json.dump({"hadiths": [{"hadithnumber": 1, "text": text,
                                    "reference": {"book": 1, "hadith": 1}}]}, f)
    write("انما الاعمال بالنيات")
    idx = HadithIndex.load(data_dir=str(tmp_path / "hadith"))
    assert idx.match("انما الاعمال بالنيات")["number"] == 1
    assert os.path.exists(str(tmp_path / "hadith" / ".cache" / "hadith_index.pkl"))
    write("كتاب الله حبل الله")
    idx2 = HadithIndex.load(data_dir=str(tmp_path / "hadith"))
    assert idx2.match("كتاب الله حبل الله")["number"] == 1
    assert idx2.match("انما الاعمال بالنيات") is None


def test_quran_index_load_uses_cache(tmp_path):
    from retrieval.quran_index import QuranIndex
    d = tmp_path / "quran"
    d.mkdir()
    for name in ("ara-quranuthmanihaf", "eng-ummmuhammad", "eng-mustafakhattaba"):
        with open(d / (name + ".json"), "w", encoding="utf-8") as f:
            json.dump({"quran": [{"chapter": 1, "verse": 1, "text": "بسم الله الرحمن الرحيم"}]}, f)
    idx = QuranIndex.load(data_dir=str(d))
    assert idx.get_verse(1, 1) is not None
    assert os.path.exists(str(d / ".cache" / "quran_index.pkl"))
    idx2 = QuranIndex.load(data_dir=str(d))
    assert idx2.get_verse(1, 1)["arabic"] == idx.get_verse(1, 1)["arabic"]
