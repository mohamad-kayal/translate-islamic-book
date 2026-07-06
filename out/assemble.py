"""Merge translated chunk markdowns into one book: title, hadith numbers, cleanup."""
import argparse
import glob
import os
import re

# Chunk-seam working notes ('*[Ornamental divider]*', '*[Blank page]*',
# '*[Ornamental page: Basmala]*') are for the orchestrator, not the reader.
_PAGE_NOTE = re.compile(r"^\*\[[^\]]*\]\*\s*$", re.M)
_EXTRA_BLANKS = re.compile(r"\n{3,}")


def assign_hadith_numbers(md):
    """Replace [[H]] with '**1.**', '**2.**'… (main) and [[HA]] with '**1-A.**'…
    (appendix). Bold — a bare line-initial 'N.' would parse as an ordered list."""
    main = {"n": 0}
    app = {"n": 0}

    def _main(_):
        main["n"] += 1
        return "**%d.**" % main["n"]

    def _app(_):
        app["n"] += 1
        return "**%d-A.**" % app["n"]

    md = re.sub(r"\[\[HA\]\]", _app, md)
    md = re.sub(r"\[\[H\]\]", _main, md)
    return md


def strip_page_notes(md):
    md = _PAGE_NOTE.sub("", md)
    return _EXTRA_BLANKS.sub("\n\n", md)


def merge(chunk_texts):
    return "\n\n".join(t.strip("\n") for t in chunk_texts)


def assemble(chunk_dir, out_path, title=None, author=None):
    files = sorted(glob.glob(os.path.join(chunk_dir, "chunk_*.md")))
    body = merge([open(f, encoding="utf-8").read() for f in files])
    body = strip_page_notes(body)
    book = assign_hadith_numbers(body)
    if title:
        # pandoc title block: becomes the HTML title page (before the ToC) and
        # the Title-styled opening paragraph in DOCX.
        head = "%% %s\n" % title
        if author:
            head += "%% %s\n" % author
        book = "%s\n%s" % (head, book)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(book)
    return book


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Assemble translated chunks into one book markdown.")
    p.add_argument("chunk_dir")
    p.add_argument("out_path")
    p.add_argument("--title", help="book title (title page + document title)")
    p.add_argument("--author", help="author line under the title")
    args = p.parse_args()
    assemble(args.chunk_dir, args.out_path, title=args.title, author=args.author)
    print("assembled -> %s" % args.out_path)
