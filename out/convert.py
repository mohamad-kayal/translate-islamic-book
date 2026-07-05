"""Convert the assembled Markdown book to DOCX (editable) + HTML (RTL, print-to-PDF)."""
import json
import os
import subprocess

# Minimal CSS: default RTL so Arabic verses/hadith lay out correctly; English runs LTR inline.
_HTML_CSS = """
body{max-width:820px;margin:2rem auto;font-family:Georgia,serif;line-height:1.7;padding:0 1rem}
:root{direction:rtl}
h1,h2,h3{font-family:system-ui,sans-serif}
blockquote{border-inline-start:3px solid #ccc;margin-inline:0;padding-inline-start:1rem;color:#333}
"""


def _pandoc(args):
    r = subprocess.run(["pandoc"] + args, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("pandoc failed: %s" % r.stderr)


def to_docx(md_path, out_path):
    _pandoc([md_path, "-f", "markdown", "-o", out_path])


def to_html(md_path, out_path):
    header = out_path + ".head.html"
    with open(header, "w", encoding="utf-8") as f:
        f.write("<style>%s</style>" % _HTML_CSS)
    try:
        _pandoc([md_path, "-f", "markdown", "-t", "html", "-s",
                 "--metadata", "dir=rtl", "--include-in-header", header, "-o", out_path])
    finally:
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
    import sys
    print(json.dumps(convert_all(sys.argv[1], sys.argv[2])))
