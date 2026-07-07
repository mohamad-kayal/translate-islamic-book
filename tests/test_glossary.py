import json

from scripts.glossary import load, diff


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
