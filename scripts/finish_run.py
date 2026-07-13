"""Assemble → lint → glossary harvest → review.md + bilingual.md, in one command.

    python -m scripts.finish_run runs/<slug> [--master data/glossary.json]
                                 [--changelog data/glossary-changelog.md]

Exits 1 when lint finds problems (the .srt is still written for inspection).
"""
import argparse
import json
import pathlib
import shutil
import sys

from subs.assemble import assemble
from subs.glossary import harvest
from subs.lint import lint_run
from subs.report import write_bilingual, write_review


def _sync_editor_glossary(master_path):
    """Keep the editor's auto-loaded glossary copy current with the master.

    Only runs for the real master (data/glossary.json) so tests passing a temp --master
    never clobber the shipped editor/glossary.json.
    """
    if pathlib.Path(master_path).resolve() != pathlib.Path("data/glossary.json").resolve():
        return
    editor_dir = pathlib.Path("editor")
    if editor_dir.is_dir():
        shutil.copyfile(master_path, editor_dir / "glossary.json")


def main():
    ap = argparse.ArgumentParser(description="see module docstring")
    ap.add_argument("run")
    ap.add_argument("--master", default="data/glossary.json")
    ap.add_argument("--changelog", default="data/glossary-changelog.md")
    args = ap.parse_args()

    stats = assemble(args.run)
    master = json.loads(pathlib.Path(args.master).read_text(encoding="utf-8"))
    lint_result = lint_run(args.run, master)
    harvest_result = harvest(args.run, args.master, args.changelog)
    write_review(args.run, stats, harvest_result, lint_result)
    write_bilingual(args.run)
    _sync_editor_glossary(args.master)

    print("cues: %(cues)d · sentences: %(sentences)d · quran: %(quran)d · "
          "hadith: %(hadith)d · fallbacks: %(fallbacks)d" % stats)
    print("glossary: %d added, %d conflicts pending"
          % (len(harvest_result["added"]), len(harvest_result["conflicts"])))
    print("lint problems: %d · warnings: %d"
          % (len(lint_result["problems"]), len(lint_result["warnings"]) + len(stats["warnings"])))
    print("output: %s" % stats["output"])
    if lint_result["problems"]:
        for p in lint_result["problems"]:
            print("PROBLEM: %s" % p)
        sys.exit(1)


if __name__ == "__main__":
    main()
