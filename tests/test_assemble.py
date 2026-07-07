import os

from out.assemble import (append_glossary, assemble, assign_hadith_numbers, merge,
                          number_quran_ayat, strip_page_notes)
from retrieval.quran_index import QuranIndex

# synthetic surah: ayah 3 carries a rub-el-hizb mark like the real dataset does
QIDX = QuranIndex({(1, 1): "بحر نهر", (1, 2): "جبل شمس", (1, 3): "۞ليل نهار"},
                  {(1, 1): "a", (1, 2): "b", (1, 3): "c"},
                  {(1, 1): "a", (1, 2): "b", (1, 3): "c"})


def _block(body, s=1, a="1-3"):
    return "<!--quran s=%d a=%s tr=saheeh-->\n%s\n<!--/quran-->" % (s, a, body)


def test_multiayah_block_gets_ayah_numbers():
    md = _block('بحر نهر جبل شمس ليل نهار [X: 1-3]\n"trans" [X: 1-3]')
    out = number_quran_ayat(md, QIDX)
    assert "بحر نهر (١) جبل شمس (٢) ليل نهار (٣) [X: 1-3]" in out
    assert '"trans" [X: 1-3]' in out


def test_single_ayah_block_is_not_numbered():
    md = _block('جبل شمس [X: 2]\n"b" [X: 2]', a="2-2")
    out = number_quran_ayat(md, QIDX)
    assert "جبل شمس [X: 2]" in out and "(٢)" not in out


def test_partial_quote_left_intact_but_marks_stripped():
    md = _block('جبل ۞شمس [X: 2]\n"b"', a="2-2")
    out = number_quran_ayat(md, QIDX)
    assert "جبل شمس [X: 2]" in out and "۞" not in out


def test_section_mark_stripped_from_multiayah_and_numbers_added():
    md = _block('بحر نهر ۞جبل شمس ليل نهار [X: 1-3]\n"t"')
    out = number_quran_ayat(md, QIDX)
    assert "۞" not in out
    assert "بحر نهر (١) جبل شمس (٢) ليل نهار (٣)" in out


def test_fallback_block_untouched():
    md = "<!--quran s=0 a=0-0 tr=fallback-->\n(something) [X]\n<!--/quran-->"
    assert number_quran_ayat(md, QIDX) == md


def test_main_hadith_numbered_sequentially():
    md = "[[H]] first\n[[H]] second\n[[H]] third"
    # bold, not bare 'N.' — pandoc parses a line-initial 'N.' as an ordered list
    assert assign_hadith_numbers(md) == "**1.** first\n**2.** second\n**3.** third"


def test_appendix_hadith_get_A_suffix_independent_sequence():
    md = "[[H]] a\n[[HA]] x\n[[H]] b\n[[HA]] y"
    assert assign_hadith_numbers(md) == "**1.** a\n**1-A.** x\n**2.** b\n**2-A.** y"


def test_hadith_markers_stripped_when_numbering_off():
    # inline-citation books: drop the marker cleanly at line start and mid-sentence
    assert assign_hadith_numbers("[[H]] On the authority of X", number=False) \
        == "On the authority of X"
    assert assign_hadith_numbers("said in the authentic hadith [[H]]:", number=False) \
        == "said in the authentic hadith:"


def test_merge_joins_with_blank_line_and_orders():
    assert merge(["# A\np1", "# B\np2"]) == "# A\np1\n\n# B\np2"


def test_page_notes_stripped():
    md = "prose\n\n*[Ornamental divider]*\n\n*[Blank page]*\n\n*[Ornamental page: Basmala]*\n\nmore"
    out = strip_page_notes(md)
    assert "Ornamental" not in out and "Blank page" not in out
    assert "prose" in out and "more" in out
    assert "\n\n\n" not in out


def test_assemble_prepends_title(tmp_path):
    (tmp_path / "chunk_0001.md").write_text("body one", encoding="utf-8")
    out = tmp_path / "book.md"
    book = assemble(str(tmp_path), str(out), title="Lights of the Prophets")
    assert book.startswith("% Lights of the Prophets\n")
    assert os.path.exists(out)


_GLOSS = {
    "terms": {
        "التزكية": {"translit": "tazkiyah", "english": "purification of the soul"},
        "الإصلاح": {"translit": "islah", "english": "reform"},
    },
    "names": {"موسى": "Musa"},
    "structure": {"القسم": "Part"},
}


def test_append_glossary_adds_section_with_terms_sorted():
    out = append_glossary("# body\n\ntext", _GLOSS)
    assert "## Glossary" in out
    # sorted by translit casefold: islah before tazkiyah
    assert out.index("islah") < out.index("tazkiyah")
    assert "::: {.glossary}" in out


def test_append_glossary_entry_format():
    out = append_glossary("body", _GLOSS)
    assert "*tazkiyah* · [التزكية]{lang=ar dir=rtl} · purification of the soul" in out


def test_append_glossary_excludes_names_and_structure():
    out = append_glossary("body", _GLOSS)
    assert "Musa" not in out and "Part" not in out and "موسى" not in out


def test_append_glossary_empty_terms_is_noop():
    assert append_glossary("body", {"terms": {}, "names": {}, "structure": {}}) == "body"
    assert append_glossary("body", {}) == "body"
