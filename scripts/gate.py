"""Is this run finished? One bar, for every format and every agent.

    python -m scripts.gate runs/<slug>

Exits 0 only when the run's deterministic checks all pass. No agent, Claude or otherwise,
may call a run done on its own judgment while this exits 1.
"""
import argparse
import json
import pathlib
import re
import sys

from out.lint import lint
from out.verify import verify
from retrieval.hadith_index import HadithIndex
from retrieval.quran_index import QuranIndex
from scripts.block_brief import check as check_block
from scripts.run_status import chunk_state
from subs.lint import lint_run


_PRINTED_COUNT = re.compile(r"except the (\d+|one) marked")


def printed_count(book):
    """How many † hadith the copyright page claims."""
    m = _PRINTED_COUNT.search(book)
    return 0 if m is None else 1 if m.group(1) == "one" else int(m.group(1))


def _kind(work):
    for name, kind in (("chunks.json", "book"), ("blocks.json", "lecture"), ("post.md", "post")):
        if (work / name).exists():
            return kind
    return None


def gate_book(run, work, quran_index, hadith_index):
    problems, notes = [], []
    state = chunk_state(str(work))
    if state["missing"]:
        problems.append("chunks not translated: %s" % state["missing"])
    if not (work / "revise-log.md").exists():
        problems.append("no revise-log.md: every chunk needs its reviser pass")
    if not (work / "book.md").exists():
        return problems + ["not assembled: run scripts.finish_book"], notes
    book = (work / "book.md").read_text(encoding="utf-8")
    report = verify(book, quran_index=quran_index, hadith_index=hadith_index)
    problems += report["problems"]
    unverified = report["hadith_sources"]["arabic_only"] + report["hadith_sources"]["unverified"]
    if "{.copyright}" in book and printed_count(book) != unverified:
        problems.append("the copyright page counts %d † hadith, the datasets say %d"
                        % (printed_count(book), unverified))
    linted = lint(str(work), glossary_path=str(work / "glossary.json"))
    problems += linted["problems"]
    for suffix in (".html", ".docx", ".pdf"):
        if not (run / "output" / (run.name + suffix)).exists():
            problems.append("missing output/%s%s" % (run.name, suffix))
    notes.append("quran %d, hadith %s, %d flagged, %d lint warnings"
                 % (report["n_quran"], report["hadith_sources"], len(report["flagged"]),
                    len(linted["warnings"])))
    return problems, notes


def gate_lecture(run, work, quran_index, hadith_index):
    problems, notes = [], []
    state = chunk_state(str(work))
    if state["missing"]:
        problems.append("blocks not translated: %s" % state["missing"])
    for n in state["done"]:
        problems += ["block %d: %s" % (n, p) for p in check_block(str(run), n, scripture=False)]
    if not (run / "output" / ("%s.en.srt" % run.name)).exists():
        return problems + ["not assembled: run scripts.finish_lecture"], notes
    master = json.loads(pathlib.Path("data/glossary.json").read_text(encoding="utf-8"))
    linted = lint_run(str(run), master, quran_index, hadith_index)
    problems += linted["problems"]
    notes.append("%d lint warnings" % len(linted["warnings"]))
    return problems, notes


def gate(run_dir):
    run = pathlib.Path(run_dir)
    work = run / "work"
    kind = _kind(work)
    if kind is None:
        return None, ["no chunks.json, blocks.json or post.md in %s" % work], []
    quran_index, hadith_index = QuranIndex.load(), HadithIndex.load()
    if kind == "post":
        from scripts.post import check as check_post
        problems, notes = check_post(run, quran_index, hadith_index)
    else:
        fn = gate_book if kind == "book" else gate_lecture
        problems, notes = fn(run, work, quran_index, hadith_index)
    return kind, problems, notes


def main():
    ap = argparse.ArgumentParser(description="see module docstring")
    ap.add_argument("run")
    args = ap.parse_args()
    kind, problems, notes = gate(args.run)
    for note in notes:
        print(note)
    for problem in problems:
        print("PROBLEM: %s" % problem)
    print("%s %s: %s" % (kind or "run", args.run,
                         "PASS" if not problems else "FAIL (%d problems)" % len(problems)))
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
