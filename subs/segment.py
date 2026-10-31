"""Word timeline → proto-segments → translation blocks.

Proto-segments are mechanical anchor units cut at speech pauses (never a linguistic claim):
``{"i", "w0", "w1", "text", "t0", "t1"}`` with ``w0..w1`` exclusive-end into the word list.
Blocks group proto-segments into ~`target_sec` of speech for one translator subagent:
``{"n", "s0", "s1", "context"}`` with ``s0..s1`` INCLUSIVE and `context` = the tail text of
the previous block (~`context_sec` of speech, context-only, never translated).
"""


def proto_segments(words, pause=0.6, max_words=14):
    segs = []
    cur = []
    for i, word in enumerate(words):
        if cur:
            gap = word["t0"] - words[i - 1]["t1"]
            if gap >= pause or len(cur) >= max_words:
                segs.append(cur)
                cur = []
        cur.append(i)
    if cur:
        segs.append(cur)
    out = []
    for n, idxs in enumerate(segs):
        w0, w1 = idxs[0], idxs[-1] + 1
        out.append({
            "i": n, "w0": w0, "w1": w1,
            "text": " ".join(words[j]["w"] for j in idxs),
            "t0": words[w0]["t0"], "t1": words[w1 - 1]["t1"],
        })
    return out


def make_blocks(segs, target_sec=180.0, context_sec=15.0):
    blocks = []
    start = 0
    acc = 0.0
    for i, seg in enumerate(segs):
        acc += seg["t1"] - seg["t0"]
        if acc >= target_sec or i == len(segs) - 1:
            blocks.append({"n": len(blocks), "s0": start, "s1": i, "context": ""})
            start = i + 1
            acc = 0.0
    for prev, block in zip(blocks, blocks[1:]):
        tail = []
        dur = 0.0
        for seg in reversed(segs[prev["s0"]:prev["s1"] + 1]):
            if dur >= context_sec:
                break
            tail.append(seg["text"])
            dur += seg["t1"] - seg["t0"]
        block["context"] = " ".join(reversed(tail))
    return blocks
