"""The master glossary CLI, shared by books, lectures and posts.

    python -m scripts.glossary prime   <work> [--pdf <book.pdf>]   # a book's starting glossary
    python -m scripts.glossary diff    <book-glossary.json>        # new entries + conflicts
    python -m scripts.glossary merge   <book-glossary.json> [--only <arabic,arabic,...>]
    python -m scripts.glossary subset  <run> --block N             # a lecture block's subset
    python -m scripts.glossary harvest <run>                       # auto-merge new, hold conflicts
    python -m scripts.glossary resolve <run> --accept <arabic,...> # apply named conflicts

Master: data/glossary.json (git-tracked); lecture and post growth is appended to
data/glossary-changelog.md. `merge` writes approved book entries AFTER the user has signed
off — never run it before sign-off. Stdlib only.
"""
import argparse
import json
import os
import pathlib
import subprocess
import unicodedata

from retrieval.glossary import (diff, harvest, load, merge, prime, resolve,  # noqa: F401
                                subset_for)

MASTER = "data/glossary.json"
CHANGELOG = "data/glossary-changelog.md"


def _write(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")


def _pdf_text(pdf):
    """The PDF's text layer, presentation-form glyphs folded (some books embed them)."""
    r = subprocess.run(["pdftotext", "-enc", "UTF-8", pdf, "-"], capture_output=True, text=True)
    return unicodedata.normalize("NFKC", r.stdout)


def _block_text(run_dir, n):
    data = json.loads((pathlib.Path(run_dir) / "work" / "blocks.json").read_text(encoding="utf-8"))
    block = data["blocks"][n]
    return " ".join(seg["text"] for seg in data["segments"][block["s0"]:block["s1"] + 1])


def main():
    ap = argparse.ArgumentParser(description="Master glossary (see module docstring).")
    ap.add_argument("command", choices=["prime", "diff", "merge", "subset", "harvest", "resolve"])
    ap.add_argument("target", help="book glossary.json, run directory, or work directory")
    ap.add_argument("--master", default=MASTER)
    ap.add_argument("--only", default=None, help="merge: comma-separated Arabic keys to include")
    ap.add_argument("--block", type=int, default=None, help="subset: block number")
    ap.add_argument("--accept", default=None, help="resolve: comma-separated Arabic keys")
    ap.add_argument("--pdf", default=None, help="prime: the book PDF (its text layer narrows "
                                                "the glossary to what the book mentions)")
    args = ap.parse_args()

    if args.command == "prime":
        dest = os.path.join(args.target, "glossary.json")
        if os.path.exists(dest):
            raise SystemExit("%s already exists — not overwriting a book's glossary" % dest)
        g = prime(load(args.master), _pdf_text(args.pdf) if args.pdf else None)
        _write(dest, g)
        print("primed %s: %d terms, %d names" % (dest, len(g["terms"]), len(g["names"])))
    elif args.command == "diff":
        print(json.dumps(diff(load(args.master), load(args.target)),
                         ensure_ascii=False, indent=2))
    elif args.command == "merge":
        only = set(args.only.split(",")) if args.only else None
        _write(args.master, merge(load(args.master), load(args.target), only=only))
        print("merged %s -> %s" % (args.target, args.master))
    elif args.command == "subset":
        if args.block is None:
            raise SystemExit("subset needs --block N")
        print(json.dumps(subset_for(_block_text(args.target, args.block), load(args.master)),
                         ensure_ascii=False, indent=2))
    elif args.command == "harvest":
        result = harvest(args.target, args.master, CHANGELOG)
        print(json.dumps({"added": sorted(result["added"]),
                          "conflicts": [c["ar"] for c in result["conflicts"]]},
                         ensure_ascii=False, indent=2))
    else:
        if not args.accept:
            raise SystemExit("resolve needs --accept ar1,ar2")
        applied = resolve(args.target, args.master, set(args.accept.split(",")))
        print("applied: %s" % ", ".join(applied) if applied else "nothing applied")


if __name__ == "__main__":
    main()
