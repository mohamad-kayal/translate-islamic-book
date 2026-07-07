"""The master glossary and the per-book diff/merge tooling.

    python -m scripts.glossary diff  <book-glossary.json> [--master data/glossary.json]
    python -m scripts.glossary merge <book-glossary.json> [--master data/glossary.json]
                                     [--only <arabic,arabic,...>]

`diff` lists a book glossary's new entries and its conflicts against the master (for the harvest
step's review.md proposals). `merge` writes approved entries into the master AFTER the user has
signed off — never run it before sign-off. Stdlib only.
"""
import argparse
import copy
import json

SECTIONS = ("terms", "names", "structure")


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _entry_differs(master_val, book_val):
    # compare ignoring the book-only 'override' key
    if isinstance(book_val, dict):
        book_val = {k: v for k, v in book_val.items() if k != "override"}
    return master_val != book_val


def diff(master, book):
    out = {"new_terms": {}, "new_names": {}, "new_structure": {}, "conflicts": []}
    for section in SECTIONS:
        m = master.get(section, {})
        for arabic, book_val in (book.get(section, {}) or {}).items():
            has_override = isinstance(book_val, dict) and "override" in book_val
            if arabic not in m:
                if not has_override:
                    out["new_%s" % section][arabic] = book_val
            elif _entry_differs(m[arabic], book_val) and not has_override:
                out["conflicts"].append({
                    "section": section, "arabic": arabic,
                    "master": m[arabic], "book": book_val,
                    "override": None,
                })
    return out


def _clean(val):
    if isinstance(val, dict):
        return {k: v for k, v in val.items() if k != "override"}
    return val


def merge(master, book, only=None):
    result = copy.deepcopy(master)
    for section in SECTIONS:
        dest = result.setdefault(section, {})
        for arabic, book_val in (book.get(section, {}) or {}).items():
            if only is not None and arabic not in only:
                continue
            clean = _clean(book_val)
            if arabic not in dest or dest[arabic] != clean:
                dest[arabic] = clean
    return result


def _write(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def main():
    ap = argparse.ArgumentParser(description="Master-glossary diff/merge (see module docstring).")
    ap.add_argument("command", choices=["diff", "merge"])
    ap.add_argument("book", help="the per-book glossary.json")
    ap.add_argument("--master", default="data/glossary.json")
    ap.add_argument("--only", default=None, help="merge: comma-separated Arabic keys to include")
    args = ap.parse_args()

    master, book = load(args.master), load(args.book)
    if args.command == "diff":
        print(json.dumps(diff(master, book), ensure_ascii=False, indent=2))
    else:
        only = set(args.only.split(",")) if args.only else None
        _write(args.master, merge(master, book, only=only))
        print("merged %s -> %s" % (args.book, args.master))


if __name__ == "__main__":
    main()
