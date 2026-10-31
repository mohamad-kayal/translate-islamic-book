import os
import subprocess
import sys

from out.assemble import (_sources_note, append_glossary, assemble, assign_hadith_numbers,
                          build_indexes, mark_own_renderings,
                          merge, number_quran_ayat, strip_page_notes, front_matter, back_matter,
                          _short_chapter)
from retrieval.quran_index import QuranIndex

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

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
    out = append_glossary("# body\n\non tazkiyah and Islah", _GLOSS)
    assert "## Glossary" in out
    # sorted by translit casefold: islah before tazkiyah
    section = out[out.index("## Glossary"):]
    assert section.index("islah") < section.index("tazkiyah")
    assert "::: {.glossary}" in out


def test_append_glossary_entry_format():
    out = append_glossary("the tazkiyah of the soul", _GLOSS)
    assert "*tazkiyah* · [التزكية]{lang=ar dir=rtl} · purification of the soul" in out


def test_append_glossary_lists_only_terms_the_book_uses():
    out = append_glossary("the tazkiyah of the soul", _GLOSS)
    assert "tazkiyah" in out and "islah" not in out
    # a whole word, not a fragment of a longer one
    assert append_glossary("tazkiyahs", _GLOSS) == "tazkiyahs"


def test_append_glossary_survives_null_renderings():
    gloss = {"terms": {"س": {"translit": None, "english": None},
                       "التزكية": {"translit": "tazkiyah", "english": "purification"}}}
    assert "tazkiyah · " not in append_glossary("no terms here", gloss)
    assert "purification" in append_glossary("tazkiyah", gloss)


def test_append_glossary_excludes_names_and_structure():
    out = append_glossary("tazkiyah", _GLOSS)
    assert "Musa" not in out and "Part" not in out and "موسى" not in out


def test_append_glossary_empty_terms_is_noop():
    assert append_glossary("body", {"terms": {}, "names": {}, "structure": {}}) == "body"
    assert append_glossary("body", {}) == "body"


_IDX_MD = """## Chapter One

<!--quran s=2 a=255-255 tr=saheeh-->
آية [X]
"t" [X]
<!--/quran-->

<!--hadith coll=bukhari num=1 conf=1.0 src=dataset-->
«متن»
"t" (al-Bukhari 1)
<!--/hadith-->

## Chapter Two

<!--quran s=1 a=1-3 tr=saheeh-->
آية [X]
"t" [X]
<!--/quran-->
"""


def test_build_indexes_has_both_sections_sorted():
    out = build_indexes(_IDX_MD)
    assert "## Index of Qur'anic Verses" in out
    assert "## Index of Hadith" in out
    # surah 1 sorts before surah 2
    assert out.index("Surah 1:1") < out.index("Surah 2:255")
    # entries are wrapped in the .index fenced div the CSS depends on
    assert "::: {.index}" in out


def test_index_entry_names_its_chapter():
    out = build_indexes(_IDX_MD)
    # the 2:255 verse lives under Chapter One; 1:1-3 under Chapter Two
    assert "Chapter One" in out and "Chapter Two" in out


def test_hadith_index_lists_collection_and_number():
    out = build_indexes(_IDX_MD)
    assert "al-Bukhari 1" in out or "Bukhari 1" in out


def test_build_indexes_empty_when_no_markers():
    assert build_indexes("## Chapter\n\nplain prose, no citations.") == ""


def test_single_ayah_renders_without_range_dash():
    out = build_indexes(_IDX_MD)
    assert "Surah 2:255" in out and "255–255" not in out


def test_index_excludes_glossary_and_index_headings_as_chapters():
    # a hadith cited under a real chapter, followed by later Glossary / Index headings
    md = """## Real Chapter

<!--hadith coll=muslim num=42 conf=1.0 src=dataset-->
«متن»
"t" (Muslim 42)
<!--/hadith-->

## Glossary

*term* · def

## Index of Qur'anic Verses

Surah 1:1 — *whatever*
"""
    out = build_indexes(md)
    assert "Muslim 42 — *Real Chapter*" in out
    # neither the Glossary nor the Index heading may become a chapter label
    assert "*Glossary*" not in out
    assert "*Index of Qur'anic Verses*" not in out


def test_coll0_fallback_hadith_skipped_from_index():
    md = """## Chapter

<!--hadith coll=0 num=0 conf=0.0 src=fallback-->
«متن»
"t"
<!--/hadith-->
"""
    out = build_indexes(md)
    # coll=0 is an unlocatable fallback — must not appear, and yields no Hadith section
    assert "0 0" not in out
    assert "## Index of Hadith" not in out
    assert out == ""


_META = {"title_en": "The Reformer's Compass", "title_ar": "بوصلة المصلح",
         "author_en": "Ahmad ibn Yusuf al-Sayyid", "author_ar": "أحمد بن يوسف السيد",
         "translator": "Mo", "edition": "First Edition", "year": "2026"}


def test_front_matter_has_cover_and_copyright_with_arabic_title():
    fm = front_matter(_META)
    assert "{.cover}" in fm and "{.copyright}" in fm
    assert "بوصلة المصلح" in fm and "The Reformer's Compass" in fm
    assert "lang=ar" in fm  # Arabic title carries lang/dir


def test_front_matter_translator_and_sacred_note_present():
    fm = front_matter(_META)
    assert "Mo" in fm
    # sacred-text sourcing note (Saheeh International + verified)
    assert "Saheeh International" in fm and "verified" in fm.lower()


def test_front_matter_omits_absent_optional_lines():
    fm = front_matter({"title_en": "X", "title_ar": "س", "author_en": "A", "author_ar": "ع"})
    assert "Edition" not in fm and "Translated by" not in fm


def test_back_matter_is_colophon():
    assert "{.colophon}" in back_matter()


def test_short_chapter_keeps_dotted_subsection_number():
    # dotted sub-sections ("5.1" vs "5.2") must stay distinguishable in the index
    assert _short_chapter("Section 5.1: Foo") == "Section 5.1"
    assert _short_chapter("Chapter 12: Long Title") == "Chapter 12"


def test_assemble_matter_writes_cover_and_colophon(tmp_path):
    # end-to-end: the wired matter path (not just the pure functions) reaches the file
    (tmp_path / "chunk_0001.md").write_text("body one", encoding="utf-8")
    out = tmp_path / "book.md"
    book = assemble(str(tmp_path), str(out), title="X", matter=True, meta=_META)
    assert "{.cover}" in book and "{.colophon}" in book
    written = (tmp_path / "book.md").read_text(encoding="utf-8")
    assert "{.cover}" in written and "{.colophon}" in written


def test_matter_drops_pandoc_title_block_so_cover_is_first(tmp_path):
    # with front matter on, the cover div is the title page and must be page one;
    # the pandoc '% title' block is suppressed (it would render above the cover)
    (tmp_path / "chunk_0001.md").write_text("## Chapter One\n\nbody one", encoding="utf-8")
    out = tmp_path / "book.md"
    book = assemble(str(tmp_path), str(out), title="X", author="A", matter=True, meta=_META)
    assert not any(ln.startswith("% ") for ln in book.splitlines())
    assert book.index("{.cover}") < book.index("Chapter One")


def test_title_block_still_emitted_without_matter(tmp_path):
    (tmp_path / "chunk_0001.md").write_text("body", encoding="utf-8")
    out = tmp_path / "book.md"
    book = assemble(str(tmp_path), str(out), title="X", author="A")
    assert book.startswith("% X\n% A\n")


def _run_cli(tmp_path, *extra):
    (tmp_path / "chunk_0001.md").write_text("body", encoding="utf-8")
    out = tmp_path / "book.md"
    cmd = [sys.executable, "-m", "out.assemble", str(tmp_path), str(out),
           "--no-numbering"] + list(extra)
    r = subprocess.run(cmd, cwd=_REPO_ROOT, capture_output=True, text=True)
    return r, out


def test_cli_matter_without_meta_errors_cleanly(tmp_path):
    # no glossary, no --title-ar: --matter must clean-error (exit 2), never traceback
    r, _ = _run_cli(tmp_path, "--matter")
    assert r.returncode == 2
    assert "Traceback" not in r.stderr and "KeyError" not in r.stderr
    assert "title_ar" in r.stderr  # names the missing required field(s)


def test_cli_matter_with_cli_meta_succeeds(tmp_path):
    # supplying the Arabic title/author on the CLI makes --matter usable without a book block
    r, out = _run_cli(tmp_path, "--title", "X", "--title-ar", "س",
                      "--author", "A", "--author-ar", "ع", "--matter")
    assert r.returncode == 0, r.stderr
    assert "{.cover}" in out.read_text(encoding="utf-8")


class _Index:
    def __init__(self, **entries):
        self.entries = entries

    def get(self, coll, num):
        return self.entries.get("%s_%s" % (coll, num))


_HADITH = ('<!--hadith coll=%s num=%s conf=1.0 src=%s-->\n'
           '«مثل»\n"%s" (Narrated by Someone 9)\n<!--/hadith-->')


def test_verified_hadith_gets_no_mark():
    md = _HADITH % ("bukhari", 1, "dataset", "The parable of the guidance")
    index = _Index(bukhari_1={"english": "Narrated X: The parable of the guidance."})
    assert mark_own_renderings(md, index) == (md, 0)


def test_rewritten_english_is_marked_even_though_the_marker_says_dataset():
    md = _HADITH % ("bukhari", 1, "dataset", "Something a model wrote instead")
    index = _Index(bukhari_1={"english": "The parable of the guidance."})
    out, n = mark_own_renderings(md, index)
    assert n == 1 and '(Narrated by Someone 9) †\n<!--/hadith-->' in out


def test_fallback_and_arabic_only_hadith_are_marked():
    md = "\n\n".join([_HADITH % ("hakim", 7, "fallback", "Own words"),
                       _HADITH % ("ahmad", 2, "arabic", "Own words too")])
    out, n = mark_own_renderings(md, _Index(ahmad_2={"english": ""}))
    assert n == 2 and out.count("†") == 2


def test_copyright_note_states_the_real_count():
    assert "except the 14 marked †" in _sources_note(14)
    assert "except the one marked †" in _sources_note(1)
    clean = _sources_note(0)
    assert "†" not in clean and "machine-checked" in clean
    assert not any("never machine" in _sources_note(n) for n in (0, 1, 14))


def test_assemble_threads_the_count_into_the_front_matter(tmp_path):
    chunks = tmp_path / "translated"
    chunks.mkdir()
    (chunks / "chunk_0001.md").write_text(
        _HADITH % ("hakim", 7, "fallback", "Own words"), encoding="utf-8")
    meta = {"title_en": "T", "title_ar": "ت", "author_en": "A", "author_ar": "أ"}
    book = assemble(str(chunks), str(tmp_path / "book.md"), hadith_index=_Index(),
                    matter=True, meta=meta)
    assert "except the one marked †" in book


def test_index_skips_unlocatable_numbers_and_prefers_the_authors_citation():
    md = ("## One\n\n"
          '<!--hadith coll=hakim num=0 conf=0 src=fallback-->\nx\n<!--/hadith-->\n'
          '<!--hadith coll=ahmad num=21500 cite=23482 conf=1.0 src=arabic-->\nx\n<!--/hadith-->\n')
    idx = build_indexes(md)
    assert "Hakim 0" not in idx and "Ahmad 23482" in idx and "21500" not in idx
