"""Convert the assembled Markdown book to DOCX (editable) + HTML (print-to-PDF).

The book's body is English prose (LTR); Quran/hadith quotations are Arabic (RTL) set
apart as distinct blocks. `_transform_markers` rewrites the `<!--quran-->`/`<!--hadith-->`
marker pairs `assemble.py` produces into pandoc fenced divs carrying a `custom-style`
(mapped to a paragraph style in reference.docx for Word) and a CSS class (for HTML) —
this only affects rendering; `verify.py` still checks the original marker-based markdown.
"""
import base64
import os
import re
import subprocess

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_HERE)
_FONT_PATH = os.path.join(_REPO_ROOT, "assets", "fonts", "AmiriQuran-Regular.ttf")
_REFERENCE_DOCX = os.path.join(_REPO_ROOT, "templates", "reference.docx")

_QURAN_BLOCK = re.compile(r"<!--quran\s+[^>]*?-->\n(.*?)\n<!--/quran-->", re.S)
_HADITH_BLOCK = re.compile(r"<!--hadith\s+[^>]*?-->\n(.*?)\n<!--/hadith-->", re.S)


def _wrap_verse(inner, ar_style, en_style):
    lines = [ln for ln in inner.split("\n") if ln.strip()]
    arabic, english = lines[0], "\n".join(lines[1:]).strip()
    return (
        '\n\n:::: {.verse}\n'
        '::: {custom-style="%s" dir="rtl"}\n%s\n:::\n\n'
        '::: {custom-style="%s" dir="ltr"}\n%s\n:::\n'
        '::::\n\n' % (ar_style, arabic, en_style, english)
    )


def _transform_markers(md):
    md = _QURAN_BLOCK.sub(lambda m: _wrap_verse(m.group(1), "QuranArabic", "QuranEnglish"), md)
    md = _HADITH_BLOCK.sub(lambda m: _wrap_verse(m.group(1), "HadithArabic", "HadithEnglish"), md)
    return md


def _font_data_uri():
    with open(_FONT_PATH, "rb") as f:
        return "data:font/ttf;base64,%s" % base64.b64encode(f.read()).decode("ascii")


# Body: English serif prose reads LTR; verse blocks isolate their own RTL Arabic +
# italic LTR translation. Palette: paper-toned neutral page, a single muted sage accent
# for Quran quotations, a muted sand accent for hadith — both low-chroma, high-contrast ink.
_HTML_CSS = """
@font-face{font-family:"Amiri Quran";src:url(__FONT_URI__) format("truetype");font-display:swap}
:root{color-scheme:light}
html{direction:ltr}
body{
  max-width:70ch;margin:3rem auto;padding:0 1.5rem;
  font-family:"Palatino Linotype",Palatino,"Book Antiqua",Georgia,serif;
  font-size:1.125rem;line-height:1.75;
  background:oklch(0.985 0.006 80);color:oklch(0.22 0.01 80);
  text-wrap:pretty;
}
h1,h2,h3,h4{font-family:system-ui,-apple-system,"Segoe UI",sans-serif;text-wrap:balance;color:oklch(0.2 0.01 80)}
h1{font-size:2rem;text-align:center;margin:0 0 2.5rem;padding-bottom:1rem;border-bottom:1px solid oklch(0.85 0.01 80)}
h2{font-size:1.5rem;margin:3.5rem 0 1.25rem;padding-top:1.5rem;border-top:2px solid oklch(0.75 0.02 155)}
h3{font-size:1.2rem;margin:2.25rem 0 1rem;color:oklch(0.32 0.04 155)}
h4{font-size:0.95rem;letter-spacing:.04em;text-transform:uppercase;margin:1.75rem 0 .75rem;color:oklch(0.4 0.03 155)}
p{margin:0 0 1.1rem}
em{font-style:italic}

.verse{
  margin:1.75rem 0;border-radius:8px;overflow:hidden;
  border:1px solid oklch(0.85 0.03 155);
}
[data-custom-style="QuranArabic"],[data-custom-style="HadithArabic"]{
  margin:0;padding:1.1rem 1.4rem .5rem;
  direction:rtl;text-align:right;unicode-bidi:isolate;
  font-family:"Amiri Quran","Traditional Arabic","Geeza Pro",serif;
  font-size:1.4rem;line-height:2.15;
}
[data-custom-style="QuranEnglish"],[data-custom-style="HadithEnglish"]{
  margin:0;padding:.5rem 1.4rem 1.1rem;
  direction:ltr;text-align:left;font-style:italic;font-size:1rem;line-height:1.65;
}
[data-custom-style="QuranArabic"]{background:oklch(0.955 0.02 155)}
[data-custom-style="QuranEnglish"]{background:oklch(0.955 0.02 155)}
[data-custom-style="HadithArabic"]{background:oklch(0.96 0.02 80)}
[data-custom-style="HadithEnglish"]{background:oklch(0.96 0.02 80)}
"""


def _pandoc(args):
    r = subprocess.run(["pandoc"] + args, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("pandoc failed: %s" % r.stderr)


def _rendered_copy(md_path):
    with open(md_path, encoding="utf-8") as f:
        md = f.read()
    rendered_path = md_path + ".rendered.md"
    with open(rendered_path, "w", encoding="utf-8") as f:
        f.write(_transform_markers(md))
    return rendered_path


def to_docx(md_path, out_path):
    rendered = _rendered_copy(md_path)
    try:
        args = [rendered, "-f", "markdown", "-o", out_path]
        if os.path.exists(_REFERENCE_DOCX):
            args += ["--reference-doc", _REFERENCE_DOCX]
        _pandoc(args)
    finally:
        os.remove(rendered)


def to_html(md_path, out_path):
    rendered = _rendered_copy(md_path)
    header = out_path + ".head.html"
    css = _HTML_CSS.replace("__FONT_URI__", _font_data_uri())
    with open(header, "w", encoding="utf-8") as f:
        f.write("<style>%s</style>" % css)
    try:
        _pandoc([rendered, "-f", "markdown", "-t", "html", "-s",
                 "--metadata", "dir=ltr", "--metadata", "lang=en",
                 "--include-in-header", header, "-o", out_path])
    finally:
        os.remove(rendered)
        if os.path.exists(header):
            os.remove(header)


def convert_all(md_path, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(md_path))[0]
    docx = os.path.join(out_dir, base + ".docx")
    html = os.path.join(out_dir, base + ".html")
    to_docx(md_path, docx)
    to_html(md_path, html)
    return {"docx": docx, "html": html}


if __name__ == "__main__":
    import json
    import sys
    print(json.dumps(convert_all(sys.argv[1], sys.argv[2])))
