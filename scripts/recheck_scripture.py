"""Bring a lecture's scripture claims in line with the verbatim check.

    python -m scripts.recheck_scripture runs/<slug> [--write]

A sentence with src "dataset" claims its English is dataset text, but a lecture sentence often
mixes a quote with the speaker's commentary. Where a real run of dataset words is there, `quote`
records it. Where there is none, the sentence is a paraphrase and is relabelled `fallback`, so
review.md lists it. Only what the block files claim changes: the subtitles do not.
"""
import argparse
import difflib
import glob
import json
import os

from retrieval.hadith_index import HadithIndex
from retrieval.quran_index import QuranIndex
from retrieval.verbatim import words
from subs.scripture import references, sentence_problem

# Fewer dataset words than this in a row is coincidence or a stock phrase, not a quotation.
MIN_RUN = 6


def longest_run(en, refs):
    """The longest stretch of `en`'s words found unbroken in a reference, as text."""
    quoted = words(en)
    best = []
    for ref in refs:
        reference = words(ref)
        m = difflib.SequenceMatcher(None, quoted, reference, autojunk=False).find_longest_match(
            0, len(quoted), 0, len(reference))
        if m.size > len(best):
            best = quoted[m.a:m.a + m.size]
    return " ".join(best)


def recheck_sentence(s, quran_index, hadith_index):
    """Fix one sentence's claim in place. Returns 'quote', 'fallback' or None."""
    if sentence_problem(s, quran_index, hadith_index) is None:
        return None
    en = (s.get("en") or "").replace("|", " ")
    run = longest_run(en, references(s["type"], s.get("ref"), quran_index, hadith_index))
    if len(run.split()) >= MIN_RUN:
        s["quote"] = run
        return "quote"
    s["src"] = "fallback"
    s["flags"] = list(s.get("flags") or []) + ["not the dataset's wording"]
    return "fallback"


def main():
    ap = argparse.ArgumentParser(description="see module docstring")
    ap.add_argument("run")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    quran_index, hadith_index = QuranIndex.load(), HadithIndex.load()
    counts = {"quote": 0, "fallback": 0}
    for path in sorted(glob.glob(os.path.join(args.run, "work", "translated", "block_*.json"))):
        with open(path, encoding="utf-8") as f:
            payload = json.load(f)
        changes = [recheck_sentence(s, quran_index, hadith_index)
                   for s in payload.get("sentences") or []]
        for change in filter(None, changes):
            counts[change] += 1
        if args.write and any(changes):
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
                f.write("\n")
    print(json.dumps({"run": args.run, "written": args.write, **counts}))


if __name__ == "__main__":
    main()
