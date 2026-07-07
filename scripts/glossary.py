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


_NEW_KEY_FOR_SECTION = {"terms": "new_terms", "names": "new_names", "structure": "new_structure"}


def merge(master, book, only=None):
    """Write approved entries from `book` into a copy of `master`.

    Reuses `diff` to classify entries so `merge`'s notion of "safe to write" matches
    what the sign-off proposals actually showed the user:
      - new_* entries (no override) are applied; `only` further restricts them to the
        named keys.
      - `override` entries are book-local deviations and are NEVER applied — `diff`
        already excludes them from new_*/conflicts, so they're untouched by construction.
      - conflicts (existing key, differing value, no override) are applied ONLY if their
        Arabic key is explicitly named in `only` — merging a conflict is an accept, and
        the user must name what they're accepting.
    """
    result = copy.deepcopy(master)
    d = diff(master, book)
    for section in SECTIONS:
        dest = result.setdefault(section, {})
        for arabic, book_val in d[_NEW_KEY_FOR_SECTION[section]].items():
            if only is not None and arabic not in only:
                continue
            dest[arabic] = _clean(book_val)
    if only:
        for c in d["conflicts"]:
            if c["arabic"] in only:
                dest = result.setdefault(c["section"], {})
                dest[c["arabic"]] = _clean(c["book"])
    return result


def _write(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
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
