"""Tolerant SRT/VTT parsing and SRT composition.

Parsers return ``(cues, warnings)``; a malformed cue becomes a warning, never a crash.
Cue dict: ``{"index": int, "start": float, "end": float, "text": str}`` — seconds, raw text
(YouTube rolling-caption overlaps are preserved here; flattening happens in subs.timeline).
"""
import re

_TS = re.compile(r"(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})")
_ARROW = re.compile(
    r"(\d{1,2}:\d{2}:\d{2}[,.]\d{1,3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[,.]\d{1,3})")


def parse_ts(s):
    m = _TS.fullmatch(s.strip())
    if not m:
        raise ValueError("bad timestamp: %r" % s)
    h, mi, sec, ms = m.groups()
    return int(h) * 3600 + int(mi) * 60 + int(sec) + int(ms.ljust(3, "0")) / 1000.0


def fmt_ts(sec):
    ms = int(round(sec * 1000))
    h, rem = divmod(ms, 3600000)
    mi, rem = divmod(rem, 60000)
    s, ms = divmod(rem, 1000)
    return "%02d:%02d:%02d,%03d" % (h, mi, s, ms)


def mmss(sec):
    """Human display time for review docs and warnings ([mm:ss], hours when needed)."""
    m, s = divmod(int(sec), 60)
    h, m = divmod(m, 60)
    return "%d:%02d:%02d" % (h, m, s) if h else "%02d:%02d" % (m, s)


def _blocks(text):
    text = text.lstrip("﻿").replace("\r\n", "\n").replace("\r", "\n")
    return [b for b in re.split(r"\n{2,}", text) if b.strip()]


def _parse_block(block, default_index):
    lines = block.strip("\n").split("\n")
    i = 0
    index = default_index
    if lines and lines[0].strip().isdigit():
        index = int(lines[0].strip())
        i = 1
    if i >= len(lines):
        return None
    m = _ARROW.search(lines[i])
    if not m:
        return None
    text = "\n".join(lines[i + 1:]).strip()
    return {"index": index, "start": parse_ts(m.group(1)),
            "end": parse_ts(m.group(2)), "text": text}


def parse_srt(text):
    cues, warnings = [], []
    for n, block in enumerate(_blocks(text), 1):
        cue = _parse_block(block, n)
        if cue is None:
            warnings.append("skipped malformed cue block: %r" % block[:60])
        elif cue["text"]:
            cues.append(cue)
    return cues, warnings


def parse_vtt(text):
    blocks = _blocks(text)
    if blocks and blocks[0].startswith("WEBVTT"):
        blocks = blocks[1:]
    cues, warnings = [], []
    for n, block in enumerate(blocks, 1):
        if block.startswith(("NOTE", "STYLE", "REGION")):
            continue
        cue = _parse_block(block, n)
        if cue is None:
            warnings.append("skipped malformed cue block: %r" % block[:60])
        elif cue["text"]:
            cues.append(cue)
    return cues, warnings


def compose_srt(cues):
    parts = []
    for n, cue in enumerate(cues, 1):
        text = "\n".join(cue["lines"]) if "lines" in cue else cue["text"]
        parts.append("%d\n%s --> %s\n%s\n" % (n, fmt_ts(cue["start"]), fmt_ts(cue["end"]), text))
    return "\n".join(parts)
