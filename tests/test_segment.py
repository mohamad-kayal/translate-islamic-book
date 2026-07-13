import pytest

from subs.segment import make_blocks, proto_segments


def _words(specs):
    """specs: list of (word, t0, t1)"""
    return [{"w": w, "t0": a, "t1": b} for w, a, b in specs]


def test_cut_at_pause():
    words = _words([("ا", 0.0, 1.0), ("ب", 1.1, 2.0), ("ج", 2.8, 3.5)])  # 0.8s gap before ج
    segs = proto_segments(words, pause=0.6, max_words=14)
    assert [s["text"] for s in segs] == ["ا ب", "ج"]
    assert segs[0]["w0"] == 0 and segs[0]["w1"] == 2
    assert segs[1]["w0"] == 2 and segs[1]["w1"] == 3
    assert segs[0]["t0"] == pytest.approx(0.0)
    assert segs[0]["t1"] == pytest.approx(2.0)


def test_max_words_hard_cap():
    words = _words([("ك%d" % i, i * 0.5, i * 0.5 + 0.5) for i in range(30)])  # no pauses
    segs = proto_segments(words, pause=0.6, max_words=14)
    assert all(s["w1"] - s["w0"] <= 14 for s in segs)
    assert segs[0]["w1"] == 14


def test_segments_cover_all_words_in_order():
    words = _words([("ك%d" % i, i, i + 0.9) for i in range(20)])
    segs = proto_segments(words, pause=0.05, max_words=14)
    spans = [(s["w0"], s["w1"]) for s in segs]
    assert spans[0][0] == 0 and spans[-1][1] == 20
    for (a, b), (c, d) in zip(spans, spans[1:]):
        assert b == c
    assert [s["i"] for s in segs] == list(range(len(segs)))


def test_blocks_group_by_target_duration():
    words = _words([("ك%d" % i, i * 2.0, i * 2.0 + 1.0) for i in range(30)])  # 1s gaps
    segs = proto_segments(words, pause=0.6, max_words=14)  # every word its own segment
    blocks = make_blocks(segs, target_sec=10.0, context_sec=4.0)
    assert blocks[0]["s0"] == 0
    assert blocks[-1]["s1"] == len(segs) - 1  # inclusive
    for a, b in zip(blocks, blocks[1:]):
        assert b["s0"] == a["s1"] + 1
    # each block ~10s of SPEECH (sum of segment durations, 1s each) -> ~10 segs per block
    assert blocks[0]["s1"] - blocks[0]["s0"] + 1 == 10


def test_block_context_is_previous_tail():
    words = _words([("ك%d" % i, i * 2.0, i * 2.0 + 1.0) for i in range(30)])
    segs = proto_segments(words, pause=0.6, max_words=14)
    blocks = make_blocks(segs, target_sec=10.0, context_sec=4.0)
    assert blocks[0]["context"] == ""
    prev_last = blocks[0]["s1"]
    assert blocks[1]["context"].split()[-1] == segs[prev_last]["text"]
    # ~4s of tail at ~2s per segment -> short
    assert len(blocks[1]["context"].split()) <= 4
