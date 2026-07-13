"""Checks on the assembled English subtitles.

``problems`` must be fixed; ``warnings`` are review items (they land in review.md).
"""
import json
import pathlib
import re

from subs.glossary import fold
from subs.retime import MAX_CPS, MAX_DUR, MAX_LINE, MAX_LINES, cps
from subs.srt_io import mmss, parse_srt

_ARABIC = re.compile("[؀-ۿݐ-ݿ]")
_ITALIC_TAG = re.compile(r"</?i>")


def lint_cues(cues):
    problems, warnings = [], []
    for i, cue in enumerate(cues, 1):
        # measure what the viewer reads, not the markup
        lines = [_ITALIC_TAG.sub("", l)
                 for l in (cue.get("lines") or cue.get("text", "").split("\n"))]
        text = " ".join(lines)
        dur = cue["end"] - cue["start"]
        at = mmss(cue["start"])
        if dur <= 0:
            problems.append("cue %d: non-positive duration" % i)
        if dur > MAX_DUR + 1e-6:
            problems.append("cue %d: duration %.2fs exceeds %.0fs" % (i, dur, MAX_DUR))
        if len(lines) > MAX_LINES:
            problems.append("cue %d: %d lines (max %d)" % (i, len(lines), MAX_LINES))
        for line in lines:
            if len(line) > MAX_LINE:
                problems.append("cue %d: line exceeds %d chars: %r" % (i, MAX_LINE, line[:50]))
        if cps(text, dur) > MAX_CPS:
            warnings.append("[%s] cue %d: reading speed %.1f cps" % (at, i, cps(text, dur)))
        if dur < 0.5:
            warnings.append("[%s] cue %d: very short (%.2fs)" % (at, i, dur))
        if _ARABIC.search(text):
            problems.append("cue %d: leftover Arabic characters: %r" % (i, text[:50]))
    for i, (a, b) in enumerate(zip(cues, cues[1:]), 1):
        if b["start"] < a["end"] - 1e-6:
            problems.append("cue %d/%d: overlap" % (i, i + 1))
    return {"problems": problems, "warnings": warnings}


def lint_run(run_dir, master):
    """Lint the emitted .srt + segment coverage + glossary drift vs the Arabic."""
    run_dir = pathlib.Path(run_dir)
    srt_path = run_dir / "output" / ("%s.en.srt" % run_dir.name)
    cues, parse_warnings = parse_srt(srt_path.read_text(encoding="utf-8"))
    for c in cues:
        c["lines"] = c["text"].split("\n")
    result = lint_cues(cues)
    result["warnings"] = list(parse_warnings) + result["warnings"]

    data = json.loads((run_dir / "work" / "blocks.json").read_text(encoding="utf-8"))
    covered = set()
    for f in sorted((run_dir / "work" / "translated").glob("block_*.json")):
        for s in json.loads(f.read_text(encoding="utf-8"))["sentences"]:
            covered.update(range(s["segs"][0], s["segs"][1] + 1))
    dispatched = set()
    for b in data["blocks"]:
        block_file = run_dir / "work" / "translated" / ("block_%03d.json" % b["n"])
        if block_file.exists():
            dispatched.update(range(b["s0"], b["s1"] + 1))
    missing = dispatched - covered
    if missing:
        result["problems"].append("segments not covered by any sentence: %s"
                                  % sorted(missing)[:20])

    arabic_folded = " %s " % fold(" ".join(
        seg["text"] for seg in data["segments"] if seg["i"] in covered))
    english = " ".join(" ".join(c["lines"]) for c in cues).lower()
    for ar, val in (master.get("terms") or {}).items():
        if " %s " % fold(ar) in arabic_folded:
            eng, translit = val.get("english", "").lower(), val.get("translit", "").lower()
            if (eng and eng not in english) and (translit and translit not in english):
                result["warnings"].append(
                    "glossary drift: %s spoken but neither %r nor %r appears in the English"
                    % (ar, val.get("english"), val.get("translit")))
    return result
