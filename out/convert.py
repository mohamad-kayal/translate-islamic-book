"""Convert the assembled Markdown book to DOCX (editable) + HTML (print-to-PDF).

The book's body is English prose (LTR); Quran/hadith quotations are Arabic (RTL) set
apart as distinct blocks. `_transform_markers` rewrites the `<!--quran-->`/`<!--hadith-->`
marker pairs `assemble.py` produces into pandoc fenced divs carrying a `custom-style`
(mapped to a paragraph style in reference.docx for Word) and a CSS class (for HTML) —
this only affects rendering; `verify.py` still checks the original marker-based markdown.
"""
import base64
import json
import os
import re
import subprocess

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_HERE)
_FONTS_DIR = os.path.join(_REPO_ROOT, "assets", "fonts")
_REFERENCE_DOCX = os.path.join(_REPO_ROOT, "templates", "reference.docx")

_QURAN_BLOCK = re.compile(r"<!--quran\s+[^>]*?-->\n(.*?)\n<!--/quran-->", re.S)
_HADITH_BLOCK = re.compile(r"<!--hadith\s+[^>]*?-->\n(.*?)\n<!--/hadith-->", re.S)
_LATIN = re.compile(r"[A-Za-z]")
_TITLE = re.compile(r"^%\s+(.+?)\s*$", re.M)
_H1 = re.compile(r"^#\s+(.+?)\s*$", re.M)


def _wrap_verse(inner, ar_style, en_style):
    # Arabic = the leading run of lines with no Latin letters (may wrap over
    # several lines); English translation = everything after.
    lines = [ln for ln in inner.split("\n") if ln.strip()]
    n_ar = 0
    while n_ar < len(lines) and not _LATIN.search(lines[n_ar]):
        n_ar += 1
    n_ar = max(n_ar, 1)
    arabic = "\n".join(lines[:n_ar])
    english = "\n".join(lines[n_ar:]).strip()
    out = (
        '\n\n:::: {.verse}\n'
        '::: {custom-style="%s" dir="rtl" lang="ar"}\n%s\n:::\n' % (ar_style, arabic)
    )
    if english:
        out += '\n::: {custom-style="%s" dir="ltr"}\n%s\n:::\n' % (en_style, english)
    return out + '::::\n\n'


def _transform_markers(md):
    md = _QURAN_BLOCK.sub(lambda m: _wrap_verse(m.group(1), "QuranArabic", "QuranEnglish"), md)
    md = _HADITH_BLOCK.sub(lambda m: _wrap_verse(m.group(1), "HadithArabic", "HadithEnglish"), md)
    return md


def _font_faces():
    """@font-face blocks for every font in assets/fonts/fonts.json, embedded as
    data URIs so the HTML is a single self-contained file."""
    with open(os.path.join(_FONTS_DIR, "fonts.json"), encoding="utf-8") as f:
        entries = json.load(f)
    faces = []
    for e in entries:
        path = os.path.join(_FONTS_DIR, e["file"])
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        if e["file"].endswith(".woff2"):
            mime, fmt = "font/woff2", "woff2"
        else:
            mime, fmt = "font/ttf", "truetype"
        rng = "unicode-range:%s;" % e["unicode_range"] if e.get("unicode_range") else ""
        faces.append(
            '@font-face{font-family:"%s";font-style:%s;font-weight:%s;'
            'src:url(data:%s;base64,%s) format("%s");font-display:swap;%s}'
            % (e["family"], e["style"], e["weight"], mime, b64, fmt, rng))
    return "\n".join(faces)


# The design brief: the interior of a serious religious publisher's hardcover —
# classical book typography (Cardo, a Bembo revival cut for classical/theological
# scholarship) with manuscript rubrication (one deep vermilion accent, the same
# red the source book uses for its own rubrics). Quran is set centered in Amiri
# Quran; hadith right-aligned in Amiri (Bulaq-press naskh). No cards, no panels:
# quotations are distinguished the way books do it — size, centering, and space.
_HTML_CSS = """
__FONT_FACES__

:root{
  color-scheme:light;
  --paper:oklch(0.988 0.002 90);
  --ink:oklch(0.24 0.012 60);
  --ink-quiet:oklch(0.35 0.012 60);
  --rubric:oklch(0.44 0.14 29);
  --rule:oklch(0.87 0.015 60);
}
html{direction:ltr;scroll-behavior:smooth}
@media (prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
body{
  margin:0 auto;max-width:34em;
  padding:clamp(1.5rem,4vh,3rem) clamp(1.1rem,5vw,2rem) 6rem;
  background:var(--paper);color:var(--ink);
  font-family:"Cardo","Amiri","Iowan Old Style",Palatino,Georgia,serif;
  font-size:1.1875rem;line-height:1.62;
  text-rendering:optimizeLegibility;
}

/* ---- Title page ---- */
header#title-block-header{margin:clamp(3rem,16vh,8rem) 0 4.5rem;text-align:center}
h1.title{
  font-weight:400;text-transform:uppercase;
  font-size:clamp(1.55rem,5vw,2.4rem);line-height:1.35;
  letter-spacing:.13em;text-wrap:balance;margin:0;color:var(--ink);
}
header#title-block-header p.author{
  margin:2.2rem 0 0;letter-spacing:.18em;text-transform:uppercase;
  font-size:.9rem;color:var(--ink-quiet);text-align:center;text-indent:0;
}
header#title-block-header::after{
  content:"\\2766";display:block;color:var(--rubric);
  font-size:1.3rem;margin-top:2rem;
}

/* ---- Contents ---- */
nav#TOC{margin:0 auto 5rem;max-width:26em}
nav#TOC::before{
  content:"Contents";display:block;text-align:center;
  letter-spacing:.22em;text-transform:uppercase;font-size:.85rem;
  color:var(--rubric);margin-bottom:1.6rem;
}
nav#TOC ul{list-style:none;margin:0;padding:0}
nav#TOC li{margin:.4rem 0;text-align:center}
nav#TOC a{color:var(--ink);text-decoration:none}
nav#TOC a:hover{color:var(--rubric)}

/* ---- Prose: justified book paragraphs with first-line indents ---- */
p{margin:0;text-align:justify;hyphens:auto;-webkit-hyphens:auto;text-wrap:pretty}
p+p{text-indent:1.45em}
ol,ul{margin:.9rem 0;padding-left:2.2em}
li{margin:.25rem 0}
li::marker{color:var(--rubric)}

/* ---- Headings ---- */
h2,h3,h4{text-wrap:balance;page-break-after:avoid}
h2{
  font-weight:400;text-align:center;color:var(--rubric);
  font-size:1.6rem;line-height:1.35;margin:4.5rem 0 2rem;
}
h2::before{content:"\\2766";display:block;font-size:1rem;margin-bottom:1.2rem}
h3{
  font-weight:700;text-align:center;color:var(--ink);
  font-size:1.17rem;margin:3.2rem 0 1.4rem;
}
h4{
  font-weight:400;text-align:center;color:var(--rubric);
  letter-spacing:.2em;text-transform:uppercase;font-size:.83rem;
  margin:2.7rem 0 1.2rem;
}

/* ---- Quran quotation: centered mushaf-style setting, no panel ---- */
.verse{margin:2.1rem auto;page-break-inside:avoid}
[data-custom-style="QuranArabic"]{
  font-family:"Amiri Quran","Amiri",serif;
  font-size:1.5rem;line-height:2.05;
  direction:rtl;unicode-bidi:isolate;text-align:center;
  margin:0 0 .9rem;padding:0 .25rem;
}
[data-custom-style="QuranEnglish"]{
  font-style:italic;text-align:center;
  font-size:1rem;line-height:1.6;color:var(--ink-quiet);
  margin:0 auto;max-width:52ch;text-indent:0;
}

/* ---- Hadith: right-aligned naskh matn + roman translation ---- */
[data-custom-style="HadithArabic"]{
  font-family:"Amiri",serif;
  font-size:1.28rem;line-height:1.95;
  direction:rtl;unicode-bidi:isolate;text-align:right;
  margin:0 0 .6rem;padding:0 1.3rem;
}
[data-custom-style="HadithEnglish"]{
  font-size:1rem;line-height:1.62;color:var(--ink-quiet);
  margin:0;padding:0 1.3rem;text-indent:0;text-align:justify;hyphens:auto;
}

hr{border:none;margin:2.6rem 0;text-align:center}
hr::after{content:"\\2766";color:var(--rubric);font-size:1rem}

/* ---- Inline Arabic inside English prose (glossary glosses, first-use terms) ---- */
[lang="ar"]{font-family:"Amiri","Amiri Quran",serif;font-size:1.06em}

/* ---- Glossary appendix: hanging-indent entries, no panel ---- */
.glossary{max-width:30em;margin:0 auto}
.glossary p{
  margin:.55rem 0;text-align:left;text-indent:0;
  padding-left:1.5em;text-indent:-1.5em;   /* hanging indent */
  line-height:1.5;
}
.glossary p em{font-style:italic;color:var(--ink)}

/* ---- Print (the book is finished by printing to PDF) ---- */
@media print{
  body{max-width:none;padding:0;font-size:11.5pt}
  header#title-block-header{margin-top:9cm;page-break-after:always}
  nav#TOC{page-break-after:always}
  h2{page-break-before:always}
  a{color:inherit;text-decoration:none}
}
@page{margin:22mm 20mm}
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
    m = _TITLE.search(md) or _H1.search(md)
    title = m.group(1) if m else os.path.splitext(os.path.basename(md_path))[0]
    return rendered_path, title


def to_docx(md_path, out_path):
    rendered, _title = _rendered_copy(md_path)
    try:
        args = [rendered, "-f", "markdown", "-o", out_path,
                "--toc", "--toc-depth", "2"]
        if os.path.exists(_REFERENCE_DOCX):
            args += ["--reference-doc", _REFERENCE_DOCX]
        _pandoc(args)
    finally:
        os.remove(rendered)


def to_html(md_path, out_path):
    rendered, title = _rendered_copy(md_path)
    header = out_path + ".head.html"
    css = _HTML_CSS.replace("__FONT_FACES__", _font_faces())
    with open(header, "w", encoding="utf-8") as f:
        f.write("<style>%s</style>" % css)
    try:
        _pandoc([rendered, "-f", "markdown", "-t", "html", "-s",
                 "--toc", "--toc-depth", "2",
                 "--metadata", "dir=ltr", "--metadata", "lang=en",
                 "--metadata", "pagetitle=%s" % title,
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
