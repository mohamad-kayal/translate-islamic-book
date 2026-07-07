"""The master glossary and the per-book diff/merge tooling.

    python -m scripts.glossary diff  <book-glossary.json> [--master data/glossary.json]
    python -m scripts.glossary merge <book-glossary.json> [--master data/glossary.json]
                                     [--only <arabic,arabic,...>]

`diff` lists a book glossary's new entries and its conflicts against the master (for the harvest
step's review.md proposals). `merge` writes approved entries into the master AFTER the user has
signed off — never run it before sign-off. Stdlib only.
"""
import argparse
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
