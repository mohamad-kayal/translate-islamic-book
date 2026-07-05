"""Merge translated chunk markdowns into one book, assigning running hadith numbers."""
import glob
import os
import re


def assign_hadith_numbers(md):
    """Replace [[H]] with '1.', '2.'… (main) and [[HA]] with '1-A.', '2-A.'… (appendix)."""
    main = {"n": 0}
    app = {"n": 0}

    def _main(_):
        main["n"] += 1
        return "%d." % main["n"]

    def _app(_):
        app["n"] += 1
        return "%d-A." % app["n"]

    md = re.sub(r"\[\[HA\]\]", _app, md)
    md = re.sub(r"\[\[H\]\]", _main, md)
    return md


def merge(chunk_texts):
    return "\n\n".join(t.strip("\n") for t in chunk_texts)


def assemble(chunk_dir, out_path):
    files = sorted(glob.glob(os.path.join(chunk_dir, "chunk_*.md")))
    body = merge([open(f, encoding="utf-8").read() for f in files])
    book = assign_hadith_numbers(body)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(book)
    return book


if __name__ == "__main__":
    import sys
    assemble(sys.argv[1], sys.argv[2])
    print("assembled -> %s" % sys.argv[2])
