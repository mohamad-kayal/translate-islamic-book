import os
import zipfile

from out import convert

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
