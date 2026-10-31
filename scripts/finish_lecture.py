"""Assemble → lint → glossary harvest → review.md + bilingual.md, in one command.

    python -m scripts.finish_lecture runs/<slug> [--master data/glossary.json]
                                     [--changelog data/glossary-changelog.md]

Exits 1 when lint finds problems (the .srt is still written for inspection).
"""
import argparse
import json
import pathlib
import shutil
import sys

from retrieval.glossary import harvest
from scripts.block_brief import load_indexes
from subs.assemble import assemble
from subs.lint import lint_run
from subs.report import write_bilingual, write_review


def sync_editor_outputs(run_dir, master_path, editor_dir="editor"):
    """Keep the editor's auto-loaded copies current: glossary.json + this run's
    bilingual.md and .en.srt land next to index.html (all gitignored except glossary).

    Only runs for the real master (data/glossary.json) so tests passing a temp --master
    never clobber the shipped editor/ copies.
    """
    if pathlib.Path(master_path).resolve() != pathlib.Path("data/glossary.json").resolve():
        return
    editor_dir = pathlib.Path(editor_dir)
    if not editor_dir.is_dir():
        return
    shutil.copyfile(master_path, editor_dir / "glossary.json")
    run_dir = pathlib.Path(run_dir)
    for f in (run_dir / "output" / ("%s.en.srt" % run_dir.name),
              run_dir / "output" / "bilingual.md"):
        if f.exists():
            shutil.copyfile(f, editor_dir / f.name)


def main():
    ap = argparse.ArgumentParser(description="see module docstring")
    ap.add_argument("run")
    ap.add_argument("--master", default="data/glossary.json")
    ap.add_argument("--changelog", default="data/glossary-changelog.md")
    ap.add_argument("--italics", action="store_true",
                    help="wrap quran/hadith cues in <i> tags in the exported SRT")
    args = ap.parse_args()

    stats = assemble(args.run, italics=args.italics)
    master = json.loads(pathlib.Path(args.master).read_text(encoding="utf-8"))
    lint_result = lint_run(args.run, master, *load_indexes())
    harvest_result = harvest(args.run, args.master, args.changelog)
    write_review(args.run, stats, harvest_result, lint_result)
    write_bilingual(args.run)
    sync_editor_outputs(args.run, args.master)

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
