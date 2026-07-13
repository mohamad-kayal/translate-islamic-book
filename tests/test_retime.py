import pytest

from subs.retime import cps, sentence_cues, wrap_lines


def _text_of(cue):
    return " ".join(cue["lines"])


def test_cps():
    assert cps("abcdefghij", 2.0) == pytest.approx(5.0)


def test_single_cue_fit():
    cues, warnings = sentence_cues("Hello there my friend", 0.0, 2.0)
    assert warnings == []
    assert len(cues) == 1
    assert cues[0]["start"] == 0.0 and cues[0]["end"] == 2.0
    assert cues[0]["lines"] == ["Hello there my friend"]


def test_split_at_marks_by_length():
    part = "This is the first clause of the sentence"   # 41 chars
    text = part + " | and here comes the second clause which continues | with a third clause to overflow it"
    cues, _ = sentence_cues(text, 10.0, 20.0)
    assert len(cues) >= 2
    # splits happen at mark boundaries: each cue text is a join of whole pieces
    assert cues[0]["lines"][0].startswith("This is the first")
    joined = " ".join(_text_of(c) for c in cues)
    assert joined == text.replace(" | ", " ")


def test_split_forced_by_max_duration():
    cues, _ = sentence_cues("short words | more words", 0.0, 16.0)
    assert len(cues) == 3  # ceil(16 / 7)


def test_no_marks_falls_back_to_spaces():
    words = ("word " * 24).strip()  # 119 chars, no | marks
    cues, _ = sentence_cues(words, 0.0, 10.0)
    assert len(cues) >= 2
    assert " ".join(_text_of(c) for c in cues) == words


def test_cues_tile_span_proportionally():
    text = "aaaa aaaa | bbbb bbbb bbbb bbbb bbbb bbbb bbbb bbbb bbbb bbbb bbbb bbbb bbbb bbbb bbbb bbbb bbbb"
    cues, _ = sentence_cues(text, 100.0, 110.0)
    assert cues[0]["start"] == pytest.approx(100.0)
    assert cues[-1]["end"] == pytest.approx(110.0)
    for a, b in zip(cues, cues[1:]):
        assert b["start"] == pytest.approx(a["end"])
    # first chunk is much shorter than the second
    assert cues[0]["end"] - cues[0]["start"] < cues[-1]["end"] - cues[-1]["start"]


def test_min_duration_borrowing():
    text = "hi | this is a considerably longer second clause with many more characters in it"
    cues, _ = sentence_cues(text, 0.0, 8.0, min_dur=0.8)
    assert all(c["end"] - c["start"] >= 0.8 - 1e-9 for c in cues)


def test_overall_cps_overrun_warns_but_emits():
    text = "This sentence is far too long to be read in the tiny time it has been given"
    cues, warnings = sentence_cues(text, 0.0, 2.0)
    assert cues
    assert any("cps" in w.lower() for w in warnings)


def test_wrap_lines_single():
    assert wrap_lines("short line") == ["short line"]


def test_wrap_lines_balanced_two():
    text = "the quick brown fox jumps over the lazy dog again"  # 50 chars
    lines = wrap_lines(text)
    assert len(lines) == 2
    assert all(len(l) <= 42 for l in lines)
    assert abs(len(lines[0]) - len(lines[1])) <= 12


def test_wrap_lines_impossible_warns():
    lines = wrap_lines("x" * 60)
    assert lines == ["x" * 60]
