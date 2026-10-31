"""Ingest a book PDF into a chunk plan.

Workflow (the agent supplies the ToC read between the two Python steps):
  1. analyze SOURCE.pdf --work WORK   -> WORK/manifest.json  (+ prints ToC candidate pages)
  2. agent reads the ToC page(s) by vision and writes WORK/structure.json:
       [{"title": "...", "start_page": N, "level": 1}, ...]
  3. chunk SOURCE.pdf --work WORK     -> WORK/chunks.json
  4. assignments --work WORK          -> WORK/assignments.md  (one brief per chunk, so a
     translator or reviser is told only "you are chunk N")
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


def _compress(nums):
    """[1,2,3,7,8] -> '1-3, 7-8'"""
    out, i = [], 0
    nums = sorted(nums)
    while i < len(nums):
        j = i
        while j + 1 < len(nums) and nums[j + 1] == nums[j] + 1:
            j += 1
        out.append(str(nums[i]) if i == j else "%d-%d" % (nums[i], nums[j]))
        i = j + 1
    return ", ".join(out)


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

    text_pages, page_class = None, {}
    manifest_path = os.path.join(args.work, "manifest.json")
    if os.path.exists(manifest_path):
        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)
        text_pages = {p["page"] for p in manifest["pages"] if p["classification"] == "text"}
        page_class = {p["page"]: p["classification"] for p in manifest["pages"]}

    ranged = structure.build_page_ranges(sections, total)
    chunks = chunker.smart_chunk(ranged, target_pages=args.target, text_pages=text_pages)
    _write(os.path.join(args.work, "chunks.json"), chunks)
    print("wrote %d chunks -> %s" % (len(chunks), os.path.join(args.work, "chunks.json")))

    # Coverage report: the orchestrator must be able to confirm every page is
    # either chunked, deliberately skipped, or knowingly front matter.
    covered, skipped = set(), set()
    for c in chunks:
        covered.update(range(c["start_page"], c["end_page"] + 1))
    for s in ranged:
        if s.get("skip"):
            skipped.update(range(s["start_page"], s["end_page"] + 1))
    uncovered = [p for p in range(1, total + 1) if p not in covered and p not in skipped]
    if skipped:
        print("skipped pages (skip=true in structure.json): %s" % _compress(skipped))
    if uncovered:
        print("NOTE — pages in no chunk (front matter?): %s" % _compress(uncovered))
    # A section 'starting' on an empty/ornamental page is the signature of a
    # printed-vs-PDF page-number offset in structure.json.
    for s in ranged:
        if not s.get("skip") and page_class.get(s["start_page"]) == "ornamental":
            print("WARNING — section '%s' starts on ornamental/empty page %d; "
                  "check for a printed-vs-PDF page offset" % (s["title"], s["start_page"]))
    return 0


def _assignments(args):
    with open(os.path.join(args.work, "structure.json"), encoding="utf-8") as f:
        levels = {s["title"]: s.get("level", 3) for s in json.load(f)}
    with open(os.path.join(args.work, "chunks.json"), encoding="utf-8") as f:
        chunks = json.load(f)
    out = ["# Chunk assignments", "",
           "WRITE each chunk to `%s/translated/chunk_NNNN.md`." % args.work, ""]
    for n, c in enumerate(chunks, 1):
        context = c.get("context_page")
        out.append("## CHUNK %04d" % n)
        out.append("Source pages **%d–%d**%s. appendix: %s."
                   % (c["start_page"], c["end_page"],
                      " (context page %d, continuity only)" % context if context else "",
                      c.get("appendix", False)))
        out.append("Section headings (place verbatim where each begins, at the given level):")
        out += ["- `%s %s`" % ("#" * levels.get(s, 3), s) for s in c["sections"]]
        out.append("")
    path = os.path.join(args.work, "assignments.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    print("wrote %s (%d chunks)" % (path, len(chunks)))
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
    s = sub.add_parser("assignments")
    s.add_argument("--work", required=True)
    s.set_defaults(fn=_assignments)
    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
