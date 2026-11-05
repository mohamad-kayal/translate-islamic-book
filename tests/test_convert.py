import os
import textwrap
import zipfile

from out import convert
from out.assemble import assign_hadith_numbers

_QURAN_MD = (
    "# Chapter\n\n"
    "<!--quran s=1 a=1-1 tr=saheeh-->\n"
    "بِسۡمِ ٱللَّهِ [الفاتحة: ١]\n"
    '"In the name of Allah" [Al-Fatihah: 1]\n'
    "<!--/quran-->\n"
)


def test_transform_markers_wraps_quran_block_in_styled_divs():
    rendered = convert._transform_markers(_QURAN_MD)
    assert '{.verse}' in rendered
    assert 'custom-style="QuranArabic" dir="rtl"' in rendered
    assert 'custom-style="QuranEnglish" dir="ltr"' in rendered
    assert "بِسۡمِ ٱللَّهِ" in rendered
    assert "In the name of Allah" in rendered
    assert "<!--quran" not in rendered


def test_to_html_contains_arabic_and_rtl(tmp_path):
    md = tmp_path / "book.md"
    md.write_text("# Chapter\n\n(بحر نهر) [Al-Fatihah: 1]\n", encoding="utf-8")
    out = tmp_path / "book.html"
    convert.to_html(str(md), str(out))
    html = out.read_text(encoding="utf-8")
    assert "بحر" in html and "dir=" in html.lower()


def test_to_html_styles_quran_block_as_verse(tmp_path):
    md = tmp_path / "book.md"
    md.write_text(_QURAN_MD, encoding="utf-8")
    out = tmp_path / "book.html"
    convert.to_html(str(md), str(out))
    html = out.read_text(encoding="utf-8")
    assert 'data-custom-style="QuranArabic"' in html
    assert 'data-custom-style="QuranEnglish"' in html
    assert "Amiri Quran" in html
    assert not os.path.exists(str(md) + ".rendered.md")  # scratch file cleaned up


def test_html_title_from_h1_and_toc(tmp_path):
    md = tmp_path / "book.md"
    md.write_text("# My Fine Book\n\n## Chapter One\n\ntext\n", encoding="utf-8")
    out = tmp_path / "book.html"
    convert.to_html(str(md), str(out))
    html = out.read_text(encoding="utf-8")
    assert "<title>My Fine Book</title>" in html
    assert "book.md.rendered" not in html
    assert 'id="TOC"' in html                      # table of contents present


def test_arabic_divs_carry_lang_ar():
    rendered = convert._transform_markers(_QURAN_MD)
    assert 'lang="ar"' in rendered


def test_wrap_verse_multiline_arabic_stays_in_arabic_div():
    md = ("<!--quran s=1 a=1-2 tr=saheeh-->\n"
          "بِسۡمِ ٱللَّهِ\n"
          "ٱلرَّحۡمَٰنِ ٱلرَّحِيمِ [الفاتحة: ١-٢]\n"
          '"In the name of Allah, the Merciful" [Al-Fatihah: 1-2]\n'
          "<!--/quran-->\n")
    rendered = convert._transform_markers(md)
    ar_start = rendered.index('custom-style="QuranArabic"')
    en_start = rendered.index('custom-style="QuranEnglish"')
    assert ar_start < rendered.index("ٱلرَّحۡمَٰنِ") < en_start


def test_to_docx_produces_zip(tmp_path):
    md = tmp_path / "book.md"
    md.write_text("# Chapter\n\ntext\n", encoding="utf-8")
    out = tmp_path / "book.docx"
    convert.to_docx(str(md), str(out))
    assert os.path.getsize(out) > 0
    with open(out, "rb") as f:
        assert f.read(2) == b"PK"        # docx is a zip


def test_to_docx_applies_quran_paragraph_styles(tmp_path):
    md = tmp_path / "book.md"
    md.write_text(_QURAN_MD, encoding="utf-8")
    out = tmp_path / "book.docx"
    convert.to_docx(str(md), str(out))
    with zipfile.ZipFile(out) as z:
        doc = z.read("word/document.xml").decode("utf-8")
    assert 'w:pStyle w:val="QuranArabic"' in doc
    assert 'w:pStyle w:val="QuranEnglish"' in doc


_SCRIPTURAL_FOOTNOTE = (
    "# Chapter\n\nBody[^n].\n\n[^n]: Introduction to the note.\n\n"
    + textwrap.indent(_QURAN_MD.split("\n\n", 1)[1], "    ")
    + "\n    [[H]] A report:\n\n"
    "    <!--hadith coll=bukhari num=1 conf=1 src=dataset-->\n"
    "    «متن»\n"
    '    "A report" (Narrated by al-Bukhari 1)\n'
    "    <!--/hadith-->\n\n"
    "    Closing explanation.\n\nBack in the main text.\n"
)


def test_transform_markers_preserves_footnote_indentation():
    rendered = convert._transform_markers(_SCRIPTURAL_FOOTNOTE)
    assert "<!--quran" not in rendered and "<!--hadith" not in rendered
    for style in ("QuranArabic", "QuranEnglish", "HadithArabic", "HadithEnglish"):
        assert '\n    ::: {custom-style="%s"' % style in rendered
    assert "\n    Closing explanation.\n" in rendered


def test_unnumbered_scriptural_footnote_stays_inside_html_note(tmp_path):
    md = tmp_path / "book.md"
    md.write_text(assign_hadith_numbers(_SCRIPTURAL_FOOTNOTE, number=False), encoding="utf-8")
    out = tmp_path / "book.html"
    convert.to_html(str(md), str(out))
    html = out.read_text(encoding="utf-8")
    note = html[html.index('<li id="fn1"'):].split("</li>", 1)[0]
    body = html[html.index("<body"):]
    for style in ("QuranArabic", "QuranEnglish", "HadithArabic", "HadithEnglish"):
        assert 'data-custom-style="%s"' % style in note
        assert body.count('data-custom-style="%s"' % style) == 1
    assert "Closing explanation." in note
    assert "Back in the main text." not in note


def test_unnumbered_scriptural_footnote_keeps_docx_styles(tmp_path):
    md = tmp_path / "book.md"
    md.write_text(assign_hadith_numbers(_SCRIPTURAL_FOOTNOTE, number=False), encoding="utf-8")
    out = tmp_path / "book.docx"
    convert.to_docx(str(md), str(out))
    with zipfile.ZipFile(out) as z:
        doc = z.read("word/document.xml").decode("utf-8")
        notes = z.read("word/footnotes.xml").decode("utf-8")
    for style in ("QuranArabic", "QuranEnglish", "HadithArabic", "HadithEnglish"):
        assert 'w:pStyle w:val="%s"' % style in notes
        assert 'w:pStyle w:val="%s"' % style not in doc
    assert "Closing explanation." in notes
    assert "Back in the main text." not in notes


# ---------------------------------------------------------------------------
# Characterization tests for _relocate_toc / _colophon_last: hand-written HTML
# fixtures mimicking the *shape* pandoc produces, without invoking pandoc.
# Both functions are pure str -> str regex surgery over the whole document.
# ---------------------------------------------------------------------------

_FOOTNOTES_SECTION = (
    '<section class="footnotes" role="doc-endnotes">\n'
    '<hr />\n'
    '<ol>\n'
    '<li id="fn1"><p>A footnote.<a href="#fnref1" class="footnote-back">↩︎</a></p>'
    '</li>\n'
    '</ol>\n'
    '</section>\n'
)

# matter HTML: nav#TOC (pandoc's default placement, before our front matter) ->
# cover -> half-title -> copyright -> body -> footnotes -> colophon -> </body>
_MATTER_HTML = (
    '<!DOCTYPE html>\n'
    '<html><head><title>Test Book</title></head>\n'
    '<body>\n'
    '<header id="title-block-header"><h1 class="title">Test Book</h1></header>\n'
    '<nav id="TOC" role="doc-toc">\n'
    '<ul>\n'
    '<li><a href="#chapter-one">Chapter One</a></li>\n'
    '</ul>\n'
    '</nav>\n'
    '<div class="cover">\n'
    '<p>[بحر نهر]{lang=ar dir=rtl}</p>\n'
    '<h1>Test Book</h1>\n'
    '<p>Author Name</p>\n'
    '</div>\n'
    '<div class="half-title">\n'
    '<p>Test Book</p>\n'
    '</div>\n'
    '<div class="copyright">\n'
    '<p><strong>Test Book</strong></p>\n'
    '<p>Author Name</p>\n'
    '</div>\n'
    '<h2 id="chapter-one">Chapter One</h2>\n'
    '<p>Body text of the chapter goes here, in prose.</p>\n'
    + _FOOTNOTES_SECTION +
    '<div class="colophon">\n'
    '<p>Set in Cardo and Amiri.</p>\n'
    '</div>\n'
    '</body>\n'
    '</html>\n'
)

# same shape, but pandoc emitted no endnotes (no footnote refs in the book)
_MATTER_HTML_NO_FOOTNOTES = _MATTER_HTML.replace(_FOOTNOTES_SECTION, "")

# non-matter HTML: plain pandoc output with a ToC but no --matter front/back matter
_NONMATTER_HTML = (
    '<!DOCTYPE html>\n'
    '<html><head><title>Plain</title></head>\n'
    '<body>\n'
    '<nav id="TOC" role="doc-toc">\n'
    '<ul>\n'
    '<li><a href="#chapter-one">Chapter One</a></li>\n'
    '</ul>\n'
    '</nav>\n'
    '<h2 id="chapter-one">Chapter One</h2>\n'
    '<p>Plain body text, no front or back matter.</p>\n'
    '</body>\n'
    '</html>\n'
)


def _tail_after_last_div_before(html, marker):
    """Substring between the closing </div> of the last div before `marker` and
    `marker` itself — used to assert nothing else sits between a relocated
    element and the tag it should be adjacent to."""
    before = html[:html.index(marker)]
    return before[before.rindex("</div>") + len("</div>"):]


def test_relocate_toc_moves_nav_after_copyright():
    result = convert._relocate_toc(_MATTER_HTML)
    assert result.index('class="copyright"') < result.index('id="TOC"')
    assert result.count('id="TOC"') == 1


def test_relocate_toc_noop_without_matter():
    # no .copyright div (and no cover/colophon) -> non-matter build, untouched
    assert convert._relocate_toc(_NONMATTER_HTML) == _NONMATTER_HTML


def test_colophon_last_is_true_last_leaf_after_footnotes():
    result = convert._colophon_last(_MATTER_HTML)
    tail = _tail_after_last_div_before(result, "</body>")
    assert tail.strip() == ""                      # nothing but whitespace after .colophon
    assert result.index('class="footnotes"') < result.index('class="colophon"')


def test_colophon_last_noop_without_matter():
    # no .colophon div -> non-matter build, untouched
    assert convert._colophon_last(_NONMATTER_HTML) == _NONMATTER_HTML


def test_colophon_last_without_footnotes_section():
    result = convert._colophon_last(_MATTER_HTML_NO_FOOTNOTES)
    tail = _tail_after_last_div_before(result, "</body>")
    assert tail.strip() == ""
    assert 'class="footnotes"' not in result
    assert 'class="colophon"' in result
