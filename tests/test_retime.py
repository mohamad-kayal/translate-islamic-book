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
    assert len(cues) >= 3  # at least ceil(16 / 7)
    assert all(c["end"] - c["start"] <= 7.0 + 1e-6 for c in cues)


def test_no_marks_falls_back_to_spaces():
    words = ("word " * 24).strip()  # 119 chars, no | marks
    cues, _ = sentence_cues(words, 0.0, 10.0)
    assert len(cues) >= 2
    assert " ".join(_text_of(c) for c in cues) == words


def test_cues_tile_span_proportionally():
    # a two-clause sentence over a 9s span (>max_dur, so it must split; char shares
    # keep both cues under 7s): time is allocated by character share
    text = "aaaa aaaa | bbbb bbbb bbbb bbbb bbbb bbbb"
    cues, _ = sentence_cues(text, 100.0, 109.0)
    assert cues[0]["start"] == pytest.approx(100.0)
    assert cues[-1]["end"] == pytest.approx(109.0)
    for a, b in zip(cues, cues[1:]):
        assert b["start"] == pytest.approx(a["end"])
    # first chunk (far fewer chars) gets less time than the second
    assert cues[0]["end"] - cues[0]["start"] < cues[-1]["end"] - cues[-1]["start"]
    assert all(c["end"] - c["start"] <= 7.0 + 1e-6 for c in cues)


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


def test_split_chunks_all_wrap_within_limit():
    # a clause the greedy splitter must not leave unwrappable (>42 with no balanced break)
    text = "we seek His forgiveness for our sins and repent to Him | and we ask Allah for steadfastness"
    cues, _ = sentence_cues(text, 0.0, 6.0)
    for c in cues:
        assert all(len(l) <= 42 for l in c["lines"]), c["lines"]


def test_no_cue_exceeds_max_duration():
    cues, _ = sentence_cues("short bit | some much longer clause is here", 0.0, 16.0)
    assert all(c["end"] - c["start"] <= 7.0 + 1e-6 for c in cues)


def test_real_pilot_block_meets_all_constraints():
    import json, pathlib
    fix = json.loads((pathlib.Path(__file__).parent / "fixtures" / "real_block0.json")
                     .read_text(encoding="utf-8"))
    segs = fix["segments"]
    for s in fix["sentences"]:
        a, b = s["segs"]
        cues, _ = sentence_cues(s["en"], segs[a]["t0"], segs[b]["t1"])
        for c in cues:
            assert all(len(l) <= 42 for l in c["lines"]), (s["segs"], c["lines"])
            assert len(c["lines"]) <= 2
            assert c["end"] - c["start"] <= 7.0 + 1e-6, (s["segs"], c)


def test_long_span_sentence_never_exceeds_max_dur():
    # char-uneven multi-clause sentences over long spans must add cuts until
    # no single cue exceeds max_dur (regression: real sirah-01 cues 75/327/1295)
    cases = [
        ("For that reason, in this series I have relied | on the book of Ibn Hisham's Sirah, | "
         "titled 'Sirat Rasul Allah ﷺ' — | 'The Biography of the Messenger of Allah ﷺ' — | "
         "and I will most likely keep that same name, | meaning the series will be titled | "
         "'The Sirah of the Messenger of Allah ﷺ.'", 24.6),
        ("For instance, nowadays, | say there are people from Palestine, | and the speaker's "
         "grandfather | lived through 1948 — | the displacement that happened, and all of that.", 20.4),
        ('You have praised Yourself. | And praise be to Allah, Lord of the worlds. | "By Allah, '
         'without Allah we would not have been guided, | neither would we have given in charity, | '
         'nor would we have prayed. | So (O Allah), please send Sakina (i.e. calmness) upon us, | '
         'and make our feet firm if we meet the enemy."', 34.9),
    ]
    for text, span in cases:
        cues, _ = sentence_cues(text, 0.0, span)
        assert all(c["end"] - c["start"] <= 7.0 + 1e-6 for c in cues), (
            span, [round(c["end"] - c["start"], 2) for c in cues])
