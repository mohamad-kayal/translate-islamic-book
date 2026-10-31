"""Assemble → verify → lint → convert → render one book, in one command.

    python -m scripts.finish_book runs/<slug> [--translator NAME] [--edition TEXT]
                                  [--year YYYY] [--numbered] [--render-anyway]

Title, author and credit come from the `book` block of <run>/work/glossary.json; flags
override it. Hadith are cited inline unless --numbered. Nothing is converted or rendered
while verify or lint report problems, unless --render-anyway.
"""
import argparse
import json
import pathlib
import subprocess
import sys

_REQUIRED = ("title_en", "title_ar", "author_en", "author_ar")


def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def main():
    ap = argparse.ArgumentParser(description="see module docstring")
    ap.add_argument("run")
    ap.add_argument("--translator")
    ap.add_argument("--edition")
    ap.add_argument("--year")
    ap.add_argument("--numbered", action="store_true",
                    help="number hadith as a collection instead of citing them inline")
    ap.add_argument("--render-anyway", action="store_true")
    args = ap.parse_args()

    run = pathlib.Path(args.run)
    slug, work, output = run.name, run / "work", run / "output"
    glossary = work / "glossary.json"
    meta = json.loads(glossary.read_text(encoding="utf-8")).get("book") or {}
    meta = {k: v for k, v in meta.items() if v}
    for key in ("translator", "edition", "year"):
        if getattr(args, key):
            meta[key] = getattr(args, key)
    missing = [k for k in _REQUIRED if not meta.get(k)]
    if missing:
        sys.exit("add %s to the `book` block of %s" % (", ".join(missing), glossary))

    cmd = [sys.executable, "-m", "out.assemble", str(work / "translated"), str(work / "book.md"),
           "--title", meta["title_en"], "--author", meta["author_en"],
           "--title-ar", meta["title_ar"], "--author-ar", meta["author_ar"],
           "--glossary", str(glossary), "--matter", "--indexes"]
    for key in ("translator", "edition", "year"):
        if meta.get(key):
            cmd += ["--" + key, str(meta[key])]
    if not args.numbered:
        cmd.append("--no-hadith-numbers")
    assembled = _run(cmd)
    if assembled.returncode:
        sys.exit("assemble failed:\n" + assembled.stderr)

    verified = json.loads(_run([sys.executable, "-m", "out.verify",
                                str(work / "book.md")]).stdout)
    linted = json.loads(_run([sys.executable, "-m", "out.lint", str(work),
                              "--glossary", str(glossary)]).stdout)
    print(json.dumps({"slug": slug, "n_quran": verified["n_quran"],
                      "n_hadith": verified["n_hadith"],
                      "hadith_sources": verified.get("hadith_sources"),
                      "verify_problems": verified["problems"],
                      "verify_flagged": len(verified["flagged"]),
                      "lint_problems": linted["problems"],
                      "lint_warnings": len(linted["warnings"])},
                     ensure_ascii=False, indent=1))
    if (verified["problems"] or linted["problems"]) and not args.render_anyway:
        sys.exit("not rendering: fix the problems above first (or pass --render-anyway)")

    converted = _run([sys.executable, "-m", "out.convert", str(work / "book.md"),
                      str(output), slug])
    if converted.returncode:
        sys.exit("convert failed:\n" + converted.stderr)
    rendered = _run([sys.executable, "-m", "scripts.render_pdf",
                     str(output / (slug + ".html")), str(output / (slug + ".pdf"))])
    if rendered.returncode:
        sys.exit("render failed:\n" + rendered.stderr)
    print("rendered %s" % (output / (slug + ".pdf")))


if __name__ == "__main__":
    main()
