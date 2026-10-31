"""Finish + verify + record one riyad episode after its translate-lecture Workflow.

    .venv/bin/python -m scripts.riyad_finish <N> [--no-commit]

Runs finish_lecture --italics, gates on lint (overlaps / any PROBLEM), sanity-checks the SRT
(0 Arabic chars, cue count, italic count), pulls the review.md stat line, updates the
episode line in data/series/riyad.md, and commits the glossary + series notes (never pushes).
Prints a single SUMMARY line; exits non-zero if a hard problem is found so the caller notices.
"""
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

from scripts import riyad_prep as prep


def run(cmd):
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)


def update_series_line(n, chapter_base, part, en_hint):
    notes = ROOT / "data" / "series" / "riyad.md"
    text = notes.read_text(encoding="utf-8")
    slug = "riyad-%02d" % n
    if ("`%s`" % slug) in text:
        return  # keep an existing (possibly hand-written) line, e.g. riyad-01
    part_note = " part %s" % part if part else ""
    label = en_hint or chapter_base
    line = "- `%s` — %s%s (%s)." % (slug, chapter_base, part_note, label)
    text = text.rstrip() + "\n" + line + "\n"
    notes.write_text(text, encoding="utf-8")


def main():
    n = int(sys.argv[1])
    no_commit = "--no-commit" in sys.argv[2:]
    slug = "riyad-%02d" % n
    run_dir = ROOT / "runs" / slug
    out_srt = run_dir / "output" / ("%s.en.srt" % slug)
    review = run_dir / "output" / "review.md"

    r = run([sys.executable, "-m", "scripts.finish_lecture", "runs/%s" % slug, "--italics"])
    log = r.stdout + r.stderr
    problems = [l for l in log.splitlines() if l.startswith("PROBLEM")]
    overlaps = [p for p in problems if "overlap" in p]
    others = [p for p in problems if "overlap" not in p]

    if not out_srt.exists():
        print("FAIL %s: finish_lecture produced no SRT" % slug)
        print(log[-1500:])
        sys.exit(2)
    bilingual = run_dir / "output" / "bilingual.md"
    if r.returncode != 0 or not review.exists() or not bilingual.exists():
        print("FAIL %s: finish_lecture exited %d; review.md=%s bilingual.md=%s"
              % (slug, r.returncode, review.exists(), bilingual.exists()))
        print(log[-1800:])
        sys.exit(2)

    srt = out_srt.read_text(encoding="utf-8")
    cues = srt.count(" --> ")
    arabic = len(re.findall(r"[؀-ۿ]", srt))
    italics = srt.count("<i>")
    stat = ""
    if review.exists():
        for l in review.read_text(encoding="utf-8").splitlines():
            if l.strip().startswith("- sentences:"):
                stat = l.strip()
                break

    hard = []
    if overlaps:
        hard.append("%d overlaps" % len(overlaps))
    if arabic:
        hard.append("%d Arabic chars left in SRT" % arabic)
    if others:
        hard.append("%d other lint problems" % len(others))

    print("SUMMARY %s: cues=%d arabic=%d italics=%d overlaps=%d other=%d%s"
          % (slug, cues, arabic, italics, len(overlaps), len(others),
             ("  [HARD: %s]" % "; ".join(hard)) if hard else "  [clean]"))
    if stat:
        print("  " + stat)
    for o in others[:8]:
        print("  " + o)

    if hard:
        sys.exit(3)

    # record + commit (glossary + series notes only; never push)
    rows = prep.parse_rows()
    _, base, part = prep.chapter_of(rows[n][1])
    update_series_line(n, base, part, prep.CHAPTER_EN.get(base))
    if not no_commit:
        run(["git", "add", "data/glossary.json", "data/glossary-changelog.md",
             "editor/glossary.json", "data/series/riyad.md"])
        c = run(["git", "commit", "-q", "-m", "glossary: %s" % slug])
        print("  committed glossary: %s" % slug if c.returncode == 0
              else "  (nothing to commit / commit skipped)")


if __name__ == "__main__":
    main()
