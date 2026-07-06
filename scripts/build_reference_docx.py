"""One-time generator for templates/reference.docx.

Starts from pandoc's own default reference.docx and restyles it to match the
HTML book design: Cardo body / Amiri Arabic, rubricated centered headings, and
four quotation paragraph styles (QuranArabic, QuranEnglish, HadithArabic,
HadithEnglish) — centered mushaf-style Quran, right-aligned naskh hadith, no
background shading (books don't put verses in colored boxes).

Re-run only if the visual design of the DOCX needs to change:
  python scripts/build_reference_docx.py templates/reference.docx
"""
import os
import re
import subprocess
import zipfile

RUBRIC = "99392B"      # deep vermilion — the source books' own rubric red
INK_QUIET = "4A463F"

_STYLES = """
  <w:style w:type="paragraph" w:styleId="QuranArabic">
    <w:name w:val="Quran Arabic" />
    <w:basedOn w:val="BodyText" />
    <w:next w:val="BodyText" />
    <w:qFormat />
    <w:pPr>
      <w:bidi />
      <w:jc w:val="center" />
      <w:spacing w:before="280" w:after="120" w:line="460" w:lineRule="atLeast" />
      <w:ind w:left="240" w:right="240" />
    </w:pPr>
    <w:rPr>
      <w:rtl />
      <w:rFonts w:cs="Amiri Quran" w:hint="cs" />
      <w:sz w:val="30" />
      <w:szCs w:val="30" />
    </w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="QuranEnglish">
    <w:name w:val="Quran English" />
    <w:basedOn w:val="BodyText" />
    <w:next w:val="BodyText" />
    <w:qFormat />
    <w:pPr>
      <w:jc w:val="center" />
      <w:spacing w:before="0" w:after="280" />
      <w:ind w:left="720" w:right="720" />
    </w:pPr>
    <w:rPr>
      <w:i />
      <w:iCs />
      <w:color w:val="%(ink_quiet)s" />
      <w:sz w:val="22" />
    </w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="HadithArabic">
    <w:name w:val="Hadith Arabic" />
    <w:basedOn w:val="BodyText" />
    <w:next w:val="BodyText" />
    <w:qFormat />
    <w:pPr>
      <w:bidi />
      <w:jc w:val="right" />
      <w:spacing w:before="280" w:after="80" w:line="420" w:lineRule="atLeast" />
      <w:ind w:left="480" w:right="480" />
    </w:pPr>
    <w:rPr>
      <w:rtl />
      <w:rFonts w:cs="Amiri" w:hint="cs" />
      <w:sz w:val="26" />
      <w:szCs w:val="26" />
    </w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="HadithEnglish">
    <w:name w:val="Hadith English" />
    <w:basedOn w:val="BodyText" />
    <w:next w:val="BodyText" />
    <w:qFormat />
    <w:pPr>
      <w:spacing w:before="0" w:after="280" />
      <w:ind w:left="480" w:right="480" />
    </w:pPr>
    <w:rPr>
      <w:color w:val="%(ink_quiet)s" />
      <w:sz w:val="22" />
    </w:rPr>
  </w:style>
""" % {"ink_quiet": INK_QUIET}


def _restyle_defaults(styles):
    """Body font: Cardo for Latin, Amiri for complex scripts."""
    return re.sub(
        r'(<w:rPrDefault>\s*<w:rPr>\s*)<w:rFonts[^/]*/>',
        r'\1<w:rFonts w:ascii="Cardo" w:hAnsi="Cardo" w:eastAsia="Cardo" w:cs="Amiri" />',
        styles, count=1)


def _restyle_block(styles, style_id, ppr_add="", rpr_add=""):
    """Inject extra pPr / rPr elements into an existing style block."""
    block_re = re.compile(
        r'(<w:style [^>]*w:styleId="%s"[^>]*>)(.*?)(</w:style>)' % style_id, re.S)
    m = block_re.search(styles)
    if not m:
        return styles
    body = m.group(2)
    if ppr_add:
        if "<w:pPr>" in body:
            body = body.replace("<w:pPr>", "<w:pPr>" + ppr_add, 1)
        else:
            body = body.replace("<w:qFormat />", "<w:qFormat /><w:pPr>%s</w:pPr>" % ppr_add, 1)
    if rpr_add:
        if "<w:rPr>" in body:
            body = body.replace("<w:rPr>", "<w:rPr>" + rpr_add, 1)
        else:
            body += "<w:rPr>%s</w:rPr>" % rpr_add
    return styles[:m.start(2)] + body + styles[m.end(2):]


def build(out_path):
    tmp = out_path + ".base.docx"
    subprocess.run(["pandoc", "-o", tmp, "--print-default-data-file", "reference.docx"], check=True)

    with zipfile.ZipFile(tmp) as src:
        names = src.namelist()
        contents = {n: src.read(n) for n in names}

    styles = contents["word/styles.xml"].decode("utf-8")
    assert "</w:styles>" in styles
    styles = _restyle_defaults(styles)
    # Title page + headings: centered, rubricated — mirrors the HTML design.
    styles = _restyle_block(styles, "Title",
                            ppr_add='<w:jc w:val="center" /><w:spacing w:before="3600" w:after="480" />')
    styles = _restyle_block(styles, "Heading1",
                            ppr_add='<w:jc w:val="center" />',
                            rpr_add='<w:color w:val="%s" />' % RUBRIC)
    styles = _restyle_block(styles, "Heading2",
                            ppr_add='<w:jc w:val="center" /><w:pageBreakBefore />',
                            rpr_add='<w:color w:val="%s" />' % RUBRIC)
    styles = _restyle_block(styles, "Heading3",
                            ppr_add='<w:jc w:val="center" />')
    styles = _restyle_block(styles, "Heading4",
                            ppr_add='<w:jc w:val="center" />',
                            rpr_add='<w:color w:val="%s" /><w:caps />' % RUBRIC)
    styles = styles.replace("</w:styles>", _STYLES + "</w:styles>")
    contents["word/styles.xml"] = styles.encode("utf-8")

    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as dst:
        for n in names:
            dst.writestr(n, contents[n])

    os.remove(tmp)


if __name__ == "__main__":
    import sys
    build(sys.argv[1] if len(sys.argv) > 1 else "templates/reference.docx")
    print("built -> %s" % (sys.argv[1] if len(sys.argv) > 1 else "templates/reference.docx"))
