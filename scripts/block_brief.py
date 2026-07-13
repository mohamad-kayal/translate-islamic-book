"""What a translator subagent reads and how its output is checked.

    python -m scripts.block_brief show  <run> --block N   # segments + context + glossary subset
    python -m scripts.block_brief check <run> --block N   # tiling check on the written block file

`show` prints everything block-specific a translator subagent needs (the general contract lives
in templates/translator-subagent.md). `check` exits 1 with the problems when the block file's
sentence ranges do not tile the block exactly — the subagent runs it as its self-check, the
orchestrator as the acceptance gate.
"""
import argparse
import json
import pathlib
import sys

from subs.assemble import validate_tiling
from subs.glossary import subset_for

MASTER = "data/glossary.json"


def _load(run_dir):
    return json.loads((pathlib.Path(run_dir) / "work" / "blocks.json").read_text(encoding="utf-8"))


def show(run_dir, n, master_path):
    data = _load(run_dir)
    block = data["blocks"][n]
    segs = data["segments"][block["s0"]:block["s1"] + 1]
    master = json.loads(pathlib.Path(master_path).read_text(encoding="utf-8"))
    subset = subset_for(" ".join(s["text"] for s in segs), master)
    out = ["BLOCK %d of %s — segments %d..%d (inclusive), %d segments"
           % (n, run_dir, block["s0"], block["s1"], len(segs)),
           "OUTPUT FILE: %s/work/translated/block_%03d.json" % (run_dir, n), ""]
    if block.get("context"):
        out.append("CONTEXT (previous speech, for continuity only — do NOT translate):")
        out.append(block["context"])
        out.append("")
    out.append("GLOSSARY (use these exact renderings):")
    out.append(json.dumps(subset, ensure_ascii=False, indent=2))
    out.append("")
    out.append("SEGMENTS [index|spoken-duration]:")
    for s in segs:
        out.append("[%d|%.1fs] %s" % (s["i"], s["t1"] - s["t0"], s["text"]))
    return "\n".join(out)


def check(run_dir, n):
    data = _load(run_dir)
    block = data["blocks"][n]
    path = pathlib.Path(run_dir) / "work" / "translated" / ("block_%03d.json" % n)
    if not path.exists():
        return ["block file missing: %s" % path]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as e:
        return ["block file is not valid JSON: %s" % e]
    if payload.get("block") != n:
        return ["block file says block=%r, expected %d" % (payload.get("block"), n)]
    sentences = payload.get("sentences") or []
    problems = validate_tiling(block, sentences)
    for i, s in enumerate(sentences):
        if not (s.get("en") or "").strip():
            problems.append("sentence %d has empty en" % i)
        if s.get("type") not in ("prose", "quran", "hadith"):
            problems.append("sentence %d has bad type %r" % (i, s.get("type")))
    return problems


def main():
    ap = argparse.ArgumentParser(description="see module docstring")
    ap.add_argument("command", choices=["show", "check"])
    ap.add_argument("run")
    ap.add_argument("--block", type=int, required=True)
    ap.add_argument("--master", default=MASTER)
    args = ap.parse_args()
    if args.command == "show":
        print(show(args.run, args.block, args.master))
    else:
        problems = check(args.run, args.block)
        if problems:
            print("PROBLEMS:")
            for p in problems:
                print("- %s" % p)
            sys.exit(1)
        print("OK: block %d tiles cleanly" % args.block)


if __name__ == "__main__":
    main()
