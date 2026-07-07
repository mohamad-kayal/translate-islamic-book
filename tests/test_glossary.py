import json
import subprocess
import sys

from scripts.glossary import load, diff, merge


def _master():
    return {
        "style": "s",
        "terms": {"التزكية": {"translit": "tazkiyah", "english": "purification of the soul"}},
        "names": {"موسى": "Musa"},
        "structure": {"القسم": "Part"},
    }


def test_load_reads_json(tmp_path):
    p = tmp_path / "g.json"
    p.write_text(json.dumps(_master(), ensure_ascii=False), encoding="utf-8")
    assert load(str(p))["terms"]["التزكية"]["translit"] == "tazkiyah"


def test_diff_finds_new_entries_in_each_section():
    book = {
        "terms": {"التزكية": {"translit": "tazkiyah", "english": "purification of the soul"},
                  "الثغور": {"translit": "thughur", "english": "the frontiers"}},
        "names": {"موسى": "Musa", "نوح": "Nuh"},
        "structure": {"القسم": "Part", "المعلم": "Signpost"},
    }
    d = diff(_master(), book)
    assert d["new_terms"] == {"الثغور": {"translit": "thughur", "english": "the frontiers"}}
    assert d["new_names"] == {"نوح": "Nuh"}
    assert d["new_structure"] == {"المعلم": "Signpost"}
    assert d["conflicts"] == []


def test_diff_flags_conflict_without_override():
    book = {"terms": {"التزكية": {"translit": "tazkiyah", "english": "inner purification"}},
            "names": {}, "structure": {}}
    d = diff(_master(), book)
    assert len(d["conflicts"]) == 1
    c = d["conflicts"][0]
    assert c["section"] == "terms" and c["arabic"] == "التزكية"
    assert c["book"]["english"] == "inner purification"
    assert d["new_terms"] == {}


def test_diff_override_is_not_a_conflict_and_not_new():
    book = {"terms": {"التزكية": {"translit": "tazkiyah", "english": "inner purification",
                                   "override": "this book's preferred sense"}},
            "names": {}, "structure": {}}
    d = diff(_master(), book)
    assert d["conflicts"] == []
    assert d["new_terms"] == {}


def test_diff_ignores_book_metadata_block():
    book = {"book": {"title_en": "X"}, "terms": {}, "names": {}, "structure": {}}
    assert diff(_master(), book)["conflicts"] == []


def test_merge_adds_new_terms_and_returns_new_object():
    master = _master()
    book = {"terms": {"الثغور": {"translit": "thughur", "english": "the frontiers"}},
            "names": {}, "structure": {}}
    merged = merge(master, book)
    assert "الثغور" in merged["terms"]
    assert "الثغور" not in master["terms"]          # input untouched


def test_merge_never_applies_override():
    master = _master()
    book = {"terms": {"التزكية": {"translit": "tazkiyah", "english": "inner purification",
                                   "override": "book sense"}},
            "names": {}, "structure": {}}
    merged = merge(master, book)
    # override is a deliberate book-local deviation — must not reach the master
    assert merged["terms"]["التزكية"] == _master()["terms"]["التزكية"]


def test_merge_never_applies_override_even_with_only():
    master = _master()
    book = {"terms": {"التزكية": {"translit": "tazkiyah", "english": "inner purification",
                                   "override": "book sense"}},
            "names": {}, "structure": {}}
    merged = merge(master, book, only={"التزكية"})
    assert merged["terms"]["التزكية"] == _master()["terms"]["التزكية"]


def test_merge_does_not_apply_conflict_by_default():
    master = _master()
    book = {"terms": {"التزكية": {"translit": "tazkiyah", "english": "inner purification"}},
            "names": {}, "structure": {}}
    merged = merge(master, book)
    assert merged["terms"]["التزكية"] == _master()["terms"]["التزكية"]


def test_merge_applies_conflict_when_named_in_only():
    master = _master()
    book = {"terms": {"التزكية": {"translit": "tazkiyah", "english": "inner purification"}},
            "names": {}, "structure": {}}
    merged = merge(master, book, only={"التزكية"})
    assert merged["terms"]["التزكية"] == {"translit": "tazkiyah", "english": "inner purification"}


def test_merge_only_filter_restricts_keys():
    master = _master()
    book = {"terms": {"الثغور": {"translit": "thughur", "english": "the frontiers"},
                      "المحكمات": {"translit": "muhkamat", "english": "firm principles"}},
            "names": {}, "structure": {}}
    merged = merge(master, book, only={"الثغور"})
    assert "الثغور" in merged["terms"] and "المحكمات" not in merged["terms"]


def test_cli_diff_prints_new_and_conflicts(tmp_path):
    master_p = tmp_path / "master.json"
    master_p.write_text(json.dumps(_master(), ensure_ascii=False), encoding="utf-8")
    book_p = tmp_path / "book.json"
    book_p.write_text(json.dumps(
        {"terms": {"الثغور": {"translit": "thughur", "english": "the frontiers"}},
         "names": {}, "structure": {}}, ensure_ascii=False), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, "-m", "scripts.glossary", "diff", str(book_p), "--master", str(master_p)],
        capture_output=True, text=True)
    assert proc.returncode == 0
    assert "الثغور" in proc.stdout and "thughur" in proc.stdout


def test_cli_merge_writes_master(tmp_path):
    master_p = tmp_path / "master.json"
    master_p.write_text(json.dumps(_master(), ensure_ascii=False), encoding="utf-8")
    book_p = tmp_path / "book.json"
    book_p.write_text(json.dumps(
        {"terms": {"الثغور": {"translit": "thughur", "english": "the frontiers"}},
         "names": {}, "structure": {}}, ensure_ascii=False), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, "-m", "scripts.glossary", "merge", str(book_p), "--master", str(master_p)],
        capture_output=True, text=True)
    assert proc.returncode == 0
    written = json.loads(master_p.read_text(encoding="utf-8"))
    assert "الثغور" in written["terms"]
