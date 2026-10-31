"""Sentence → cues: all subtitle timestamp math lives here (the model never does timing).

``sentence_cues(en_marked, t0, t1)`` takes a translated sentence whose ``|`` marks are the
model's clause-boundary break candidates and the sentence's spoken span, and returns
``([{"start", "end", "lines"}], warnings)``:

1. If the whole sentence fits one cue (≤ `max_lines`·`max_line` chars, ≤ `max_dur`,
   ≤ `max_cps`) it becomes one cue.
2. Otherwise it is split into ``k = max(ceil(chars/percue), ceil(dur/max_dur))`` cues at the
   mark boundaries nearest the ideal proportional positions (falling back to spaces when the
   model gave too few marks).
3. Chunk durations are allocated proportionally by character count over ``[t0, t1]``,
   butt-joined, with a borrowing pass that keeps every cue ≥ `min_dur`.
4. An overall reading speed above `max_cps` cannot be fixed by splitting — the cue is emitted
   with a warning (the translator was instructed to condense; lint surfaces the residue).
"""
import math

MAX_LINE = 42
MAX_LINES = 2
MAX_CPS = 20.0
MIN_DUR = 0.8
MAX_DUR = 7.0


def cps(text, dur):
    if dur <= 0:
        return float("inf")
    return len(text.replace("\n", "")) / dur


def wrap_lines(text, width=MAX_LINE, max_lines=MAX_LINES):
    if len(text) <= width:
        return [text]
    best = None
    for i, ch in enumerate(text):
        if ch != " ":
            continue
        left, right = text[:i], text[i + 1:]
        if len(left) <= width and len(right) <= width:
            bal = abs(len(left) - len(right))
            if best is None or bal < best[0]:
                best = (bal, [left, right])
    if best:
        return best[1]
    return [text]  # no valid break — caller/lint flags the overlong line


def _split_positions(text, k, marks):
    """Choose k-1 cut positions (char indexes into text) nearest ideal proportions."""
    candidates = sorted(marks)
    if len(candidates) < k - 1:
        extra = [i for i, ch in enumerate(text) if ch == " " and i not in marks]
        candidates = sorted(candidates + extra)
    cuts = []
    prev = 0
    remaining = list(candidates)
    for j in range(1, k):
        ideal = j * len(text) / k
        usable = [c for c in remaining if c > prev]
        if not usable:
            break
        pick = min(usable, key=lambda c: abs(c - ideal))
        cuts.append(pick)
        prev = pick
        remaining = [c for c in remaining if c > pick]
    return cuts


def _cap_max_dur(spans, max_dur):
    """Donate any span's excess over max_dur to the roomiest neighbor (fixpoint exists
    whenever sum(spans) <= len(spans)*max_dur, which choosing k >= ceil(dur/max_dur) ensures)."""
    for _ in range(len(spans) * 3):
        over = [i for i, d in enumerate(spans) if d > max_dur + 1e-9]
        if not over:
            return True
        i = over[0]
        neighbors = [j for j in (i - 1, i + 1) if 0 <= j < len(spans) and spans[j] < max_dur]
        if not neighbors:
            return False
        j = min(neighbors, key=lambda j: spans[j])
        move = min(spans[i] - max_dur, max_dur - spans[j])
        spans[i] -= move
        spans[j] += move
    return all(d <= max_dur + 1e-9 for d in spans)


def _borrow_min_dur(spans, min_dur):
    """spans: mutable list of durations tiling the sentence span."""
    for _ in range(len(spans) * 2):
        short = [i for i, d in enumerate(spans) if d < min_dur - 1e-9]
        if not short:
            return True
        i = short[0]
        neighbors = [j for j in (i - 1, i + 1) if 0 <= j < len(spans)]
        donor = max(neighbors, key=lambda j: spans[j], default=None)
        if donor is None or spans[donor] - (min_dur - spans[i]) < min_dur:
            return False
        spans[donor] -= min_dur - spans[i]
        spans[i] = min_dur
    return all(d >= min_dur - 1e-9 for d in spans)


def sentence_cues(en_marked, t0, t1, max_cps=MAX_CPS, max_line=MAX_LINE,
                  max_lines=MAX_LINES, min_dur=MIN_DUR, max_dur=MAX_DUR):
    warnings = []
    pieces = [p.strip() for p in en_marked.split("|") if p.strip()]
    text = " ".join(pieces)
    dur = t1 - t0
    if not text or dur <= 0:
        return [], ["empty sentence or non-positive span [%s, %s]" % (t0, t1)]

    if cps(text, dur) > max_cps:
        warnings.append("reading speed %.1f cps exceeds %.0f (span %.2fs, %d chars)"
                        % (cps(text, dur), max_cps, dur, len(text)))

    def _wraps(chunk):
        return all(len(l) <= max_line for l in wrap_lines(chunk, max_line, max_lines))

    per_cue = max_line * max_lines
    if dur <= max_dur and _wraps(text):
        return [{"start": t0, "end": t1, "lines": wrap_lines(text, max_line, max_lines)}], warnings

    # char positions in `text` where a piece boundary's separating space sits
    marks = []
    pos = 0
    for piece in pieces[:-1]:
        pos += len(piece)
        marks.append(pos)  # index of the joining space
        pos += 1
    k = max(math.ceil(len(text) / per_cue), math.ceil(dur / max_dur), 1)
    max_k = text.count(" ") + 1

    def _chunks_and_spans(k):
        cuts = _split_positions(text, k, marks)
        chunks = []
        prev = 0
        for c in cuts:
            chunks.append(text[prev:c].strip())
            prev = c + 1
        chunks.append(text[prev:].strip())
        chunks = [c for c in chunks if c]
        total = float(sum(len(c) for c in chunks))
        spans = [dur * len(c) / total for c in chunks]
        return chunks, spans

    while True:
        chunks, spans = _chunks_and_spans(k)
        # escalate k until every chunk both wraps and fits max_dur by char-share
        # (more cuts shrink the largest proportional span toward the dur/k mean)
        if (all(_wraps(c) for c in chunks) and max(spans) <= max_dur + 1e-9) or k >= max_k:
            break
        k += 1
    for chunk in chunks:
        if not _wraps(chunk):
            warnings.append("unbreakable overlong line: %r" % chunk[:50])
    if not _cap_max_dur(spans, max_dur):
        warnings.append("could not keep every cue under %.1fs (span %.2fs, %d cues)"
                        % (max_dur, dur, len(chunks)))
    if not _borrow_min_dur(spans, min_dur):
        warnings.append("could not keep every cue above %.1fs (span %.2fs, %d cues)"
                        % (min_dur, dur, len(chunks)))
    cues = []
    t = t0
    for i, (chunk, d) in enumerate(zip(chunks, spans)):
        end = t1 if i == len(chunks) - 1 else t + d
        cues.append({"start": t, "end": end, "lines": wrap_lines(chunk, max_line, max_lines)})
        t = end
    return cues, warnings
