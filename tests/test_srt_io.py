import pathlib

import pytest

from subs.srt_io import compose_srt, fmt_ts, parse_srt, parse_ts, parse_vtt

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "sample_head.srt"


def test_parse_ts_comma_and_dot():
    assert parse_ts("00:00:06,600") == pytest.approx(6.6)
    assert parse_ts("00:00:06.600") == pytest.approx(6.6)
    assert parse_ts("01:20:37,199") == pytest.approx(4837.199)


def test_fmt_ts_round_trip():
    assert fmt_ts(6.6) == "00:00:06,600"
    assert fmt_ts(4837.199) == "01:20:37,199"
    assert parse_ts(fmt_ts(0.001)) == pytest.approx(0.001)


def test_parse_real_sample_head():
    cues, warnings = parse_srt(FIXTURE.read_text(encoding="utf-8-sig"))
    assert warnings == []
    assert cues[0]["index"] == 1
    assert cues[0]["start"] == pytest.approx(0.199)
    assert cues[0]["end"] == pytest.approx(6.6)
    assert cues[0]["text"].startswith("الحمد لله حمدا كثيرا")
    # rolling captions: overlaps are preserved raw at parse time
    assert cues[1]["start"] < cues[0]["end"]
    assert len(cues) == 20


def test_parse_skips_malformed_cue_with_warning():
    text = "1\n00:00:00,000 --> 00:00:02,000\nok one\n\ngarbage without timestamp\n\n3\n00:00:04,000 --> 00:00:06,000\nok two\n"
    cues, warnings = parse_srt(text)
    assert [c["text"] for c in cues] == ["ok one", "ok two"]
    assert len(warnings) == 1


def test_parse_multiline_and_crlf():
    text = "1\r\n00:00:00,000 --> 00:00:02,000\r\nline one\r\nline two\r\n\r\n"
    cues, _ = parse_srt(text)
    assert cues[0]["text"] == "line one\nline two"


def test_compose_reindexes_and_formats():
    cues = [
        {"start": 0.2, "end": 2.0, "lines": ["Hello there,", "friend"]},
        {"start": 2.0, "end": 4.5, "text": "Second cue"},
    ]
    out = compose_srt(cues)
    assert out == (
        "1\n00:00:00,200 --> 00:00:02,000\nHello there,\nfriend\n\n"
        "2\n00:00:02,000 --> 00:00:04,500\nSecond cue\n"
    )


def test_parse_vtt_basic():
    text = "WEBVTT\n\n00:00:00.000 --> 00:00:02.500\nfirst\n\n00:00:02.500 --> 00:00:04.000\nsecond\n"
    cues, warnings = parse_vtt(text)
    assert warnings == []
    assert cues[0]["start"] == pytest.approx(0.0)
    assert cues[0]["end"] == pytest.approx(2.5)
    assert cues[1]["text"] == "second"
