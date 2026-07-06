import os

from out.assemble import assemble, assign_hadith_numbers, merge, strip_page_notes


def test_main_hadith_numbered_sequentially():
    md = "[[H]] first\n[[H]] second\n[[H]] third"
    # bold, not bare 'N.' — pandoc parses a line-initial 'N.' as an ordered list
    assert assign_hadith_numbers(md) == "**1.** first\n**2.** second\n**3.** third"


def test_appendix_hadith_get_A_suffix_independent_sequence():
    md = "[[H]] a\n[[HA]] x\n[[H]] b\n[[HA]] y"
    assert assign_hadith_numbers(md) == "**1.** a\n**1-A.** x\n**2.** b\n**2-A.** y"


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
