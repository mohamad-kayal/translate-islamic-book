"""The run's human-facing deliverables besides the .srt: review.md + bilingual.md."""
import json
import pathlib


def _load_run(run_dir):
    run_dir = pathlib.Path(run_dir)
    data = json.loads((run_dir / "work" / "blocks.json").read_text(encoding="utf-8"))
    sentences = []
    for f in sorted((run_dir / "work" / "translated").glob("block_*.json")):
        sentences.extend(json.loads(f.read_text(encoding="utf-8"))["sentences"])
    return data["segments"], sentences


def _mmss(sec):
    m, s = divmod(int(sec), 60)
    h, m = divmod(m, 60)
    return "%d:%02d:%02d" % (h, m, s) if h else "%02d:%02d" % (m, s)


def write_bilingual(run_dir):
    run_dir = pathlib.Path(run_dir)
    segments, sentences = _load_run(run_dir)
    lines = ["# Bilingual review — %s" % run_dir.name, ""]
    for s in sentences:
        a, b = s["segs"]
        arabic = " ".join(seg["text"] for seg in segments[a:b + 1])
        tag = "" if s.get("type") == "prose" else "  `%s%s`" % (
            s.get("type"), " " + s["ref"] if s.get("ref") else "")
        lines.append("**[%s]**%s" % (_mmss(segments[a]["t0"]), tag))
        lines.append("<div dir=\"rtl\">%s</div>" % arabic)
        lines.append("")
        lines.append(" ".join(s["en"].replace("|", " ").split()))
        lines.append("")
    out = run_dir / "output" / "bilingual.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def write_review(run_dir, stats, harvest_result, lint_result):
    run_dir = pathlib.Path(run_dir)
    segments, sentences = _load_run(run_dir)
    lines = ["# Review — %s" % run_dir.name, "",
             "- sentences: %(sentences)d · cues: %(cues)d · quran: %(quran)d · "
             "hadith: %(hadith)d · fallbacks: %(fallbacks)d" % stats, ""]

    scripture = [s for s in sentences if s.get("type") in ("quran", "hadith")]
    if scripture:
        lines.append("## Scripture")
        for s in scripture:
            a, _ = s["segs"]
            lines.append("- [%s] %s %s (%s)%s" % (
                _mmss(segments[a]["t0"]), s["type"], s.get("ref") or "?",
                s.get("src") or "?",
                " — " + "; ".join(s["flags"]) if s.get("flags") else ""))
        lines.append("")

    flagged = [s for s in sentences if s.get("flags") and s.get("type") == "prose"]
    if flagged:
        lines.append("## Flagged sentences")
        for s in flagged:
            a, _ = s["segs"]
            lines.append("- [%s] %s — %s" % (
                _mmss(segments[a]["t0"]), "; ".join(s["flags"]),
                s["en"].replace("|", " ")[:80]))
        lines.append("")

    lines.append("## Glossary")
    added = harvest_result.get("added", {})
    if added:
        lines.append("Auto-merged this run:")
        for ar, info in added.items():
            val = info["value"]
            rendered = val if isinstance(val, str) else "%s, %s" % (val["translit"], val["english"])
            lines.append("- %s: %s → %s" % (info["section"], ar, rendered))
    else:
        lines.append("No new terms harvested.")
    conflicts = harvest_result.get("conflicts", [])
    if conflicts:
        lines.append("")
        lines.append("**Conflicts pending your call** (apply with "
                     "`python -m scripts.glossary resolve <run> --accept <arabic,...>`):")
        for c in conflicts:
            master_val, proposed = c["master"], c["proposed"]
            fmt = lambda v: v if isinstance(v, str) else "%s, %s" % (v.get("translit", ""), v.get("english", ""))
            lines.append("- %s: master has %r, run proposes %r" % (c["ar"], fmt(master_val), fmt(proposed)))
    lines.append("")

    if lint_result.get("problems"):
        lines.append("## Lint problems (must fix)")
        lines.extend("- %s" % p for p in lint_result["problems"])
        lines.append("")
    warnings = list(stats.get("warnings", [])) + list(lint_result.get("warnings", []))
    if warnings:
        lines.append("## Warnings")
        lines.extend("- %s" % w for w in warnings)
        lines.append("")

    out = run_dir / "output" / "review.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out
