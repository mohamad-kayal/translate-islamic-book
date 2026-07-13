"""Translated block JSONs → the English .srt (via retime) + run stats.

``validate_tiling`` is the contract check on a subagent's output: its sentences' inclusive
``segs`` ranges must tile the block's ``[s0, s1]`` exactly — no gap, no overlap, in order.
"""
import json
import pathlib

from subs.retime import sentence_cues
from subs.srt_io import compose_srt, mmss


def validate_tiling(block, sentences):
    problems = []
    expected = block["s0"]
    for s in sentences:
        a, b = s["segs"]
        if a > b:
            problems.append("sentence range [%d, %d] is inverted" % (a, b))
        elif a < expected:
            problems.append("sentence range [%d, %d] overlaps/misordered (expected start %d)"
                            % (a, b, expected))
        elif a > expected:
            problems.append("gap: segments %d..%d uncovered" % (expected, a - 1))
        expected = max(expected, b + 1)
    if expected != block["s1"] + 1:
        problems.append("block tail uncovered: expected coverage through %d, got %d"
                        % (block["s1"], expected - 1))
    return problems


def _load(path):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def load_translated(run_dir):
    """Returns (segments, [(block, sentences), ...] sorted by block n)."""
    run_dir = pathlib.Path(run_dir)
    data = _load(run_dir / "work" / "blocks.json")
    blocks = {b["n"]: b for b in data["blocks"]}
    out = []
    for f in sorted((run_dir / "work" / "translated").glob("block_*.json")):
        payload = _load(f)
        out.append((blocks[payload["block"]], payload["sentences"]))
    out.sort(key=lambda pair: pair[0]["n"])
    return data["segments"], out


def assemble(run_dir, italics=False):
    run_dir = pathlib.Path(run_dir)
    segments, translated = load_translated(run_dir)
    cues, warnings = [], []
    stats = {"sentences": 0, "quran": 0, "hadith": 0, "fallbacks": 0}
    for block, sentences in translated:
        tiling = validate_tiling(block, sentences)
        if tiling:
            warnings.extend("block %d: %s" % (block["n"], p) for p in tiling)
        for s in sentences:
            a, b = s["segs"]
            t0, t1 = segments[a]["t0"], segments[b]["t1"]
            sent_cues, sent_warnings = sentence_cues(s["en"], t0, t1)
            if italics and s.get("type") in ("quran", "hadith"):
                for cue in sent_cues:
                    cue["lines"] = ["<i>%s</i>" % l for l in cue["lines"]]
            cues.extend(sent_cues)
            warnings.extend("[%s] %s" % (mmss(t0), w) for w in sent_warnings)
            stats["sentences"] += 1
            if s.get("type") in ("quran", "hadith"):
                stats[s["type"]] += 1
                if s.get("src") == "fallback":
                    stats["fallbacks"] += 1
    out_dir = run_dir / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / ("%s.en.srt" % run_dir.name)
    out_path.write_text(compose_srt(cues), encoding="utf-8")
    stats["cues"] = len(cues)
    stats["warnings"] = warnings
    stats["output"] = str(out_path)
    return stats
