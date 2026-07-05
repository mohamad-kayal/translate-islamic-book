import os

from out import convert


def test_to_html_contains_arabic_and_rtl(tmp_path):
    md = tmp_path / "book.md"
    md.write_text("# Chapter\n\n(بحر نهر) [Al-Fatihah: 1]\n", encoding="utf-8")
    out = tmp_path / "book.html"
    convert.to_html(str(md), str(out))
    html = out.read_text(encoding="utf-8")
    assert "بحر" in html and "dir=" in html.lower()


def test_to_docx_produces_zip(tmp_path):
    md = tmp_path / "book.md"
    md.write_text("# Chapter\n\ntext\n", encoding="utf-8")
    out = tmp_path / "book.docx"
    convert.to_docx(str(md), str(out))
    assert os.path.getsize(out) > 0
    with open(out, "rb") as f:
        assert f.read(2) == b"PK"        # docx is a zip
