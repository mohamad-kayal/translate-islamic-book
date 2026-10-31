import json

from scripts.gate import _kind, gate_book, gate_lecture


class _Quran:
    def get_verse(self, s, a):
        return {"arabic": "بحر نهر", "saheeh": "sea river", "clear": "x"} if (s, a) == (1, 1) else None


class _Hadith:
    def get(self, coll, num):
        return None


BOOK = ('## One\n\n<!--quran s=1 a=1-1 tr=saheeh-->\nبحر نهر [ر]\n"%s" [Al-Fatihah: 1]\n<!--/quran-->\n')


def _book(tmp_path, english="sea river"):
    run = tmp_path / "runs" / "b1"
    work = run / "work"
    (work / "translated").mkdir(parents=True)
    (run / "output").mkdir()
    (work / "chunks.json").write_text('[{"sections": ["One"], "start_page": 1, "end_page": 2}]')
    (work / "glossary.json").write_text('{"terms": {}, "names": {}}')
    (work / "revise-log.md").write_text("chunk 0001 CLEAN")
    (work / "translated" / "chunk_0001.md").write_text(BOOK % english, encoding="utf-8")
    (work / "book.md").write_text(BOOK % english, encoding="utf-8")
    for suffix in (".html", ".docx", ".pdf"):
        (run / "output" / ("b1" + suffix)).write_text("x")
    return run


def _gate(run):
    return gate_book(run, run / "work", _Quran(), _Hadith())[0]


def test_a_finished_book_passes(tmp_path):
    assert _gate(_book(tmp_path)) == []


def test_a_rewritten_verse_fails(tmp_path):
    assert any("English deviates" in p for p in _gate(_book(tmp_path, "the ocean, the stream")))


def test_skipping_the_reviser_fails(tmp_path):
    run = _book(tmp_path)
    (run / "work" / "revise-log.md").unlink()
    assert any("reviser" in p for p in _gate(run))


def test_a_missing_chunk_fails(tmp_path):
    run = _book(tmp_path)
    (run / "work" / "translated" / "chunk_0001.md").unlink()
    assert any("not translated" in p for p in _gate(run))


def test_a_missing_deliverable_fails(tmp_path):
    run = _book(tmp_path)
    (run / "output" / "b1.pdf").unlink()
    assert any("b1.pdf" in p for p in _gate(run))


def test_an_unassembled_book_fails_without_crashing(tmp_path):
    run = _book(tmp_path)
    (run / "work" / "book.md").unlink()
    assert any("not assembled" in p for p in _gate(run))


def test_kind_is_read_from_the_plan_file(tmp_path):
    assert _kind(tmp_path) is None
    (tmp_path / "post.md").write_text("x")
    assert _kind(tmp_path) == "post"
    (tmp_path / "blocks.json").write_text("{}")
    assert _kind(tmp_path) == "lecture"
    (tmp_path / "chunks.json").write_text("[]")
    assert _kind(tmp_path) == "book"


def _lecture(tmp_path, monkeypatch, sentence):
    run = tmp_path / "s1"
    work = run / "work"
    (work / "translated").mkdir(parents=True)
    (run / "output").mkdir()
    (work / "blocks.json").write_text(json.dumps({
        "segments": [{"i": 0, "t0": 0.0, "t1": 3.0, "text": "نص"}],
        "blocks": [{"n": 0, "s0": 0, "s1": 0, "context": ""}]}, ensure_ascii=False))
    (work / "translated" / "block_000.json").write_text(json.dumps(
        {"block": 0, "sentences": [sentence], "new_terms": [], "flags": []}), encoding="utf-8")
    (run / "output" / "s1.en.srt").write_text("1\n00:00:00,000 --> 00:00:03,000\nsea river\n")
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "glossary.json").write_text('{"terms": {}}')
    monkeypatch.chdir(tmp_path)
    return run


def test_a_lecture_with_true_claims_passes(tmp_path, monkeypatch):
    run = _lecture(tmp_path, monkeypatch, {"segs": [0, 0], "type": "quran", "ref": "1:1",
                                           "src": "dataset", "en": "sea river"})
    assert gate_lecture(run, run / "work", _Quran(), _Hadith())[0] == []


def test_a_lecture_claiming_dataset_for_its_own_words_fails(tmp_path, monkeypatch):
    run = _lecture(tmp_path, monkeypatch, {"segs": [0, 0], "type": "quran", "ref": "1:1",
                                           "src": "dataset", "en": "the ocean"})
    problems = gate_lecture(run, run / "work", _Quran(), _Hadith())[0]
    assert any("not the dataset's wording" in p for p in problems)
