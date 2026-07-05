"""Ingest a book PDF into a chunk plan.

Workflow (the agent supplies the ToC read between the two Python steps):
  1. analyze SOURCE.pdf --work WORK   -> WORK/manifest.json  (+ prints ToC candidate pages)
  2. agent reads the ToC page(s) by vision and writes WORK/structure.json:
       [{"title": "...", "start_page": N, "level": 1}, ...]
  3. chunk SOURCE.pdf --work WORK     -> WORK/chunks.json
"""
import argparse
import json
import os
import sys

from ingest import chunk as chunker
from ingest import pages, structure


def _write(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def _analyze(args):
    manifest = pages.analyze_book(args.pdf)
    os.makedirs(args.work, exist_ok=True)
    _write(os.path.join(args.work, "manifest.json"), manifest)
    orn = [p["page"] for p in manifest["pages"] if p["classification"] == "ornamental"]
    print("total_pages: %d" % manifest["total_pages"])
    print("toc_candidate_pages: %s" % structure.locate_toc_pages(args.pdf))
    print("ornamental_pages: %s" % orn)
    print("wrote %s" % os.path.join(args.work, "manifest.json"))
    return 0


def _chunk(args):
    with open(os.path.join(args.work, "structure.json"), encoding="utf-8") as f:
        sections = json.load(f)
    total = pages.page_count(args.pdf)
    problems = structure.validate_structure(sections, total)
    if problems:
        print("STRUCTURE INVALID:", file=sys.stderr)
        for p in problems:
            print("  - " + p, file=sys.stderr)
        return 2
    ranged = structure.build_page_ranges(sections, total)
    chunks = chunker.smart_chunk(ranged, target_pages=args.target)
    _write(os.path.join(args.work, "chunks.json"), chunks)
    print("wrote %d chunks -> %s" % (len(chunks), os.path.join(args.work, "chunks.json")))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description="Ingest a book PDF into a chunk plan.")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("analyze")
    a.add_argument("pdf")
    a.add_argument("--work", required=True)
    a.set_defaults(fn=_analyze)
    c = sub.add_parser("chunk")
    c.add_argument("pdf")
    c.add_argument("--work", required=True)
    c.add_argument("--target", type=int, default=10)
    c.set_defaults(fn=_chunk)
    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
