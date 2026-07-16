"""Ingest a YouTube URL or a caption file into a run directory.

    python -m scripts.ingest_video <url-or-file> --run runs/<slug>
                                   [--pause 0.6] [--block-sec 180] [--lang ar]

Writes ``work/timeline.json`` (word timeline) and ``work/blocks.json`` (proto-segments +
translation blocks) and prints run stats. A URL is fetched with yt-dlp (json3 auto-captions,
word-level timing); a ``.srt``/``.vtt`` file goes through the tolerant parser + rolling-caption
overlap flattening.
"""
import argparse
import json
import pathlib
import subprocess
import sys

from subs.segment import make_blocks, proto_segments
from subs.srt_io import parse_srt, parse_vtt
from subs.timeline import words_from_cues, words_from_json3


def is_url(s):
    return s.startswith(("http://", "https://", "www.", "youtube.com", "youtu.be"))


def fetch_json3(url, work, lang="ar"):
    """yt-dlp auto-captions → path of the downloaded json3 file."""
    template = str(work / "captions")
    # YouTube's default web client now gates auto-caption fetches behind a PO token
    # ("The page needs to be reloaded"); the android client still serves json3 cleanly.
    cmd = [sys.executable, "-m", "yt_dlp",
           "--skip-download", "--write-auto-subs", "--write-subs",
           "--extractor-args", "youtube:player_client=android",
           "--sub-langs", lang, "--sub-format", "json3", "-o", template, url]
    subprocess.run(cmd, check=True)
    hits = sorted(work.glob("captions*.json3"))
    if not hits:
        raise SystemExit("yt-dlp produced no %s json3 captions for %s" % (lang, url))
    return hits[0]


def ingest(source, run_dir, pause=0.6, block_sec=180.0, lang="ar"):
    run_dir = pathlib.Path(run_dir)
    work = run_dir / "work"
    work.mkdir(parents=True, exist_ok=True)
    warnings = []
    if is_url(source):
        path = fetch_json3(source, work, lang)
        words = words_from_json3(json.loads(path.read_text(encoding="utf-8")))
        kind = "json3"
    else:
        path = pathlib.Path(source)
        text = path.read_text(encoding="utf-8-sig")
        if path.suffix.lower() == ".vtt" or text.lstrip().startswith("WEBVTT"):
            cues, warnings = parse_vtt(text)
            kind = "vtt"
        else:
            cues, warnings = parse_srt(text)
            kind = "srt"
        words = words_from_cues(cues)
    if not words:
        raise SystemExit("no caption words found in %s" % source)

    (work / "timeline.json").write_text(json.dumps(
        {"source": str(source), "kind": kind, "words": words}, ensure_ascii=False),
        encoding="utf-8")
    segments = proto_segments(words, pause=pause)
    blocks = make_blocks(segments, target_sec=block_sec)
    (work / "blocks.json").write_text(json.dumps(
        {"segments": segments, "blocks": blocks}, ensure_ascii=False), encoding="utf-8")
    return {"kind": kind, "words": len(words), "segments": len(segments),
            "blocks": len(blocks), "duration": words[-1]["t1"], "warnings": warnings}


def main():
    ap = argparse.ArgumentParser(description="see module docstring")
    ap.add_argument("source", help="YouTube URL or .srt/.vtt file")
    ap.add_argument("--run", required=True, help="run directory, e.g. runs/<slug>")
    ap.add_argument("--pause", type=float, default=0.6)
    ap.add_argument("--block-sec", type=float, default=180.0)
    ap.add_argument("--lang", default="ar")
    args = ap.parse_args()
    stats = ingest(args.source, args.run, args.pause, args.block_sec, args.lang)
    for w in stats["warnings"]:
        print("WARN:", w, file=sys.stderr)
    print("kind=%(kind)s words=%(words)d segments=%(segments)d blocks=%(blocks)d "
          "duration=%(duration).1fs" % stats)


if __name__ == "__main__":
    main()
