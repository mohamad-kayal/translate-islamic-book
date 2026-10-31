"""Normalize captions into the pipeline's core structure: the word timeline.

A word: ``{"w": str, "t0": float, "t1": float}`` (seconds).

YouTube rolling-caption SRT exports carry OVERLAPPING cue times (each cue stays on screen
while the next appears). The effective spoken span of cue N is ``[start_N, start_{N+1})``
whenever the next cue starts inside it; a normal (non-overlapping) SRT is left untouched.
Word times inside a span are allocated proportionally by character length. Bracketed noise
tags (``[موسيقى]``, ``[تصفيق]``…) are dropped; their time becomes silence.
"""
import re

_NOISE = re.compile(r"\[[^\]]*\]")


def _cue_words(text):
    return _NOISE.sub(" ", text).split()


def words_from_cues(cues):
    words = []
    for i, cue in enumerate(cues):
        start, end = cue["start"], cue["end"]
        if i + 1 < len(cues):
            nxt = cues[i + 1]["start"]
            if start < nxt < end:
                end = nxt
        toks = _cue_words(cue["text"])
        if not toks or end <= start:
            continue
        weights = [len(t) for t in toks]
        total = float(sum(weights))
        span = end - start
        t = start
        acc = 0
        for tok, w in zip(toks, weights):
            acc += w
            t1 = end if acc == total else start + span * acc / total
            words.append({"w": tok, "t0": t, "t1": t1})
            t = t1
    return words


def words_from_json3(obj):
    words = []
    for ev in obj.get("events", []):
        segs = ev.get("segs")
        if not segs:
            continue
        t_start = ev.get("tStartMs", 0) / 1000.0
        t_end = t_start + ev.get("dDurationMs", 0) / 1000.0
        pending = []
        for seg in segs:
            tok = seg.get("utf8", "").strip()
            if not tok or _NOISE.fullmatch(tok):
                continue
            t0 = t_start + seg.get("tOffsetMs", 0) / 1000.0
            pending.append({"w": tok, "t0": t0, "t1": None})
        for cur, nxt in zip(pending, pending[1:]):
            cur["t1"] = nxt["t0"]
        if pending:
            pending[-1]["t1"] = max(t_end, pending[-1]["t0"])
        words.extend(pending)
    # YouTube json3 auto-caption events use rolling windows that overlap the next event, so a
    # word's end (esp. an event's last word, stamped to the event end) can run past the next
    # word's start. Clamp each end to the next start so proto-segments — and the cues built
    # from them — never overlap. Matches the rolling-overlap flattening in words_from_cues.
    for cur, nxt in zip(words, words[1:]):
        if cur["t1"] > nxt["t0"]:
            cur["t1"] = max(cur["t0"], nxt["t0"])
    return words
