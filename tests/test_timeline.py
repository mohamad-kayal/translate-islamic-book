import pathlib

import pytest

from subs.srt_io import parse_srt
from subs.timeline import words_from_cues, words_from_json3

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "sample_head.srt"


def _cue(start, end, text):
    return {"index": 0, "start": start, "end": end, "text": text}


def test_overlap_flatten_clamps_to_next_start():
    words = words_from_cues([_cue(0.0, 6.0, "اول ثاني"), _cue(3.0, 9.0, "ثالث")])
    # cue 1's effective span is [0.0, 3.0): its words end at 3.0
    assert words[1]["t1"] == pytest.approx(3.0)
    assert words[2]["t0"] == pytest.approx(3.0)
    assert words[2]["t1"] == pytest.approx(9.0)  # last cue keeps its own end


def test_normal_srt_untouched():
    words = words_from_cues([_cue(0.0, 2.0, "واحد"), _cue(2.5, 4.0, "اثنان")])
    assert words[0]["t1"] == pytest.approx(2.0)
    assert words[1]["t0"] == pytest.approx(2.5)


def test_degenerate_next_start_keeps_own_end():
    words = words_from_cues([_cue(5.0, 8.0, "كلمه"), _cue(5.0, 9.0, "اخرى")])
    assert words[0]["t1"] == pytest.approx(8.0)


def test_words_proportional_by_chars_and_cover_span():
    words = words_from_cues([_cue(0.0, 6.0, "اب جيمدال")])  # 2 chars vs 6 chars
    assert len(words) == 2
    assert words[0]["t0"] == pytest.approx(0.0)
    assert words[0]["t1"] == pytest.approx(1.5)  # 2/8 of 6s
    assert words[1]["t0"] == pytest.approx(1.5)
    assert words[1]["t1"] == pytest.approx(6.0)  # last word ends exactly at span end


def test_bracket_noise_tags_dropped():
    words = words_from_cues([_cue(0.0, 4.0, "[موسيقى]"), _cue(4.0, 6.0, "كلام [تصفيق] حقيقي")])
    assert [w["w"] for w in words] == ["كلام", "حقيقي"]


def test_real_sample_monotonic():
    cues, _ = parse_srt(FIXTURE.read_text(encoding="utf-8-sig"))
    words = words_from_cues(cues)
    assert len(words) > 100
    for a, b in zip(words, words[1:]):
        assert b["t0"] >= a["t0"]
        assert a["t1"] > a["t0"]


def test_words_from_json3():
    obj = {"events": [
        {"tStartMs": 1000, "dDurationMs": 3000, "segs": [
            {"utf8": "الحمد", "tOffsetMs": 0},
            {"utf8": " لله", "tOffsetMs": 1200},
        ]},
        {"tStartMs": 4000, "dDurationMs": 2000, "segs": [{"utf8": "\n"}]},
        {"tStartMs": 5000, "dDurationMs": 1500, "segs": [{"utf8": "رب", "tOffsetMs": 0}]},
    ]}
    words = words_from_json3(obj)
    assert [w["w"] for w in words] == ["الحمد", "لله", "رب"]
    assert words[0]["t0"] == pytest.approx(1.0)
    assert words[1]["t0"] == pytest.approx(2.2)
    assert words[1]["t1"] == pytest.approx(4.0)  # ends at event end
    assert words[2]["t1"] == pytest.approx(6.5)
