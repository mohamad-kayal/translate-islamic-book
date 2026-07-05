"""One-time generator for templates/reference.docx.

Starts from pandoc's own default reference.docx and injects four paragraph styles
(QuranArabic, QuranEnglish, HadithArabic, HadithEnglish) so that fenced divs tagged
`custom-style="QuranArabic"` etc. in the assembled book render as right-aligned,
bidi Arabic and italic English citation blocks in Word — instead of plain paragraphs.

Re-run only if the visual design of the DOCX verse blocks needs to change.
"""
import os
import subprocess
import zipfile

_STYLES = """
  <w:style w:type="paragraph" w:styleId="QuranArabic">
    <w:name w:val="Quran Arabic" />
    <w:basedOn w:val="BodyText" />
    <w:next w:val="BodyText" />
    <w:qFormat />
    <w:pPr>
      <w:bidi />
      <w:jc w:val="right" />
      <w:spacing w:before="240" w:after="0" w:line="440" w:lineRule="atLeast" />
      <w:ind w:left="480" w:right="480" />
      <w:shd w:val="clear" w:color="auto" w:fill="EAF2EC" />
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
      <w:spacing w:before="0" w:after="240" />
      <w:ind w:left="480" w:right="480" />
      <w:shd w:val="clear" w:color="auto" w:fill="EAF2EC" />
    </w:pPr>
    <w:rPr>
      <w:i />
      <w:iCs />
    </w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="HadithArabic">
    <w:name w:val="Hadith Arabic" />
    <w:basedOn w:val="QuranArabic" />
    <w:next w:val="BodyText" />
    <w:qFormat />
    <w:pPr>
      <w:bidi />
      <w:jc w:val="right" />
      <w:spacing w:before="240" w:after="0" w:line="440" w:lineRule="atLeast" />
      <w:ind w:left="480" w:right="480" />
      <w:shd w:val="clear" w:color="auto" w:fill="F2EDE3" />
    </w:pPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="HadithEnglish">
    <w:name w:val="Hadith English" />
    <w:basedOn w:val="QuranEnglish" />
    <w:next w:val="BodyText" />
    <w:qFormat />
    <w:pPr>
      <w:spacing w:before="0" w:after="240" />
      <w:ind w:left="480" w:right="480" />
      <w:shd w:val="clear" w:color="auto" w:fill="F2EDE3" />
    </w:pPr>
  </w:style>
"""


def build(out_path):
    tmp = out_path + ".base.docx"
    subprocess.run(["pandoc", "-o", tmp, "--print-default-data-file", "reference.docx"], check=True)

    with zipfile.ZipFile(tmp) as src:
        names = src.namelist()
        contents = {n: src.read(n) for n in names}

    styles = contents["word/styles.xml"].decode("utf-8")
    assert "</w:styles>" in styles
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
