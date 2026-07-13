"""Live-glossary CLI.

    python -m scripts.glossary subset  <run> --block N   # glossary subset for one block (JSON)
    python -m scripts.glossary harvest <run>             # auto-merge new terms, hold conflicts
    python -m scripts.glossary resolve <run> --accept ar1,ar2   # apply named conflicts

Master: data/glossary.json (git-tracked); growth is appended to data/glossary-changelog.md.
"""
import argparse
import json
import pathlib

from subs.glossary import harvest, resolve, subset_for

MASTER = "data/glossary.json"
CHANGELOG = "data/glossary-changelog.md"


def _block_text(run_dir, n):
    data = json.loads((pathlib.Path(run_dir) / "work" / "blocks.json").read_text(encoding="utf-8"))
    block = data["blocks"][n]
    return " ".join(seg["text"] for seg in data["segments"][block["s0"]:block["s1"] + 1])


def main():
    ap = argparse.ArgumentParser(description="see module docstring")
    ap.add_argument("command", choices=["subset", "harvest", "resolve"])
    ap.add_argument("run", help="run directory")
    ap.add_argument("--block", type=int, default=None)
    ap.add_argument("--accept", default=None, help="resolve: comma-separated Arabic keys")
    ap.add_argument("--master", default=MASTER)
    args = ap.parse_args()

    if args.command == "subset":
        if args.block is None:
            raise SystemExit("subset needs --block N")
        master = json.loads(pathlib.Path(args.master).read_text(encoding="utf-8"))
        print(json.dumps(subset_for(_block_text(args.run, args.block), master),
                         ensure_ascii=False, indent=2))
    elif args.command == "harvest":
        result = harvest(args.run, args.master, CHANGELOG)
        print(json.dumps({"added": sorted(result["added"]),
                          "conflicts": [c["ar"] for c in result["conflicts"]]},
                         ensure_ascii=False, indent=2))
    else:
        if not args.accept:
            raise SystemExit("resolve needs --accept ar1,ar2")
        applied = resolve(args.run, args.master, set(args.accept.split(",")))
        print("applied: %s" % ", ".join(applied) if applied else "nothing applied")


if __name__ == "__main__":
    main()
