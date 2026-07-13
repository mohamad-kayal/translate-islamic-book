import json
import pathlib

import pytest

from subs.assemble import assemble, validate_tiling
from subs.lint import lint_cues, lint_run

SEGMENTS = [
    {"i": 0, "w0": 0, "w1": 2, "text": "الحمد لله", "t0": 0.0, "t1": 2.0},
    {"i": 1, "w0": 2, "w1": 4, "text": "رب العالمين", "t0": 2.1, "t1": 4.0},
    {"i": 2, "w0": 4, "w1": 6, "text": "وبه نستعين", "t0": 4.8, "t1": 7.0},
]
BLOCK = {"n": 0, "s0": 0, "s1": 2, "context": ""}


def _sentence(a, b, en, **kw):
    s = {"segs": [a, b], "type": "prose", "en": en, "ref": None, "src": None, "flags": []}
    s.update(kw)
    return s


def test_validate_tiling_ok():
    sents = [_sentence(0, 1, "one"), _sentence(2, 2, "two")]
    assert validate_tiling(BLOCK, sents) == []


def test_validate_tiling_gap_overlap_misorder():
    assert validate_tiling(BLOCK, [_sentence(0, 0, "x"), _sentence(2, 2, "y")])  # gap at 1
    assert validate_tiling(BLOCK, [_sentence(0, 1, "x"), _sentence(1, 2, "y")])  # overlap
    assert validate_tiling(BLOCK, [_sentence(2, 2, "y"), _sentence(0, 1, "x")])  # misorder
    assert validate_tiling(BLOCK, [_sentence(0, 1, "x")])  # missing tail


def _make_run(tmp_path):
    run = tmp_path / "sirah-01"
    work = run / "work"
    (work / "translated").mkdir(parents=True)
    (work / "blocks.json").write_text(json.dumps(
        {"segments": SEGMENTS, "blocks": [BLOCK]}, ensure_ascii=False), encoding="utf-8")
    sentences = [
        _sentence(0, 1, "Praise be to Allah, | Lord of the worlds", type="quran", ref="1:2", src="dataset"),
        _sentence(2, 2, "and He is the One we ask for help"),
    ]
    (work / "translated" / "block_000.json").write_text(json.dumps(
        {"block": 0, "sentences": sentences, "new_terms": [], "flags": []},
        ensure_ascii=False), encoding="utf-8")
    return run


def test_assemble_writes_srt_and_stats(tmp_path):
    run = _make_run(tmp_path)
    stats = assemble(run)
    out = (run / "output" / "sirah-01.en.srt").read_text(encoding="utf-8")
    assert out.startswith("1\n00:00:00,000 --> ")
    assert "Praise be to Allah," in out
    assert stats["sentences"] == 2 and stats["quran"] == 1 and stats["cues"] >= 2
    # cue timing comes from segment spans
    assert "00:00:04,800" in out


def test_lint_cues_rules():
    good = [{"start": 0.0, "end": 2.0, "lines": ["hello"]},
            {"start": 2.0, "end": 4.0, "lines": ["world"]}]
    r = lint_cues(good)
    assert r["problems"] == []

    overlap = [{"start": 0.0, "end": 3.0, "lines": ["a"]}, {"start": 2.0, "end": 4.0, "lines": ["b"]}]
    assert any("overlap" in p for p in lint_cues(overlap)["problems"])

    long_line = [{"start": 0.0, "end": 2.0, "lines": ["x" * 43]}]
    assert any("42" in p for p in lint_cues(long_line)["problems"])

    three_lines = [{"start": 0.0, "end": 2.0, "lines": ["a", "b", "c"]}]
    assert any("lines" in p for p in lint_cues(three_lines)["problems"])

    fast = [{"start": 0.0, "end": 1.0, "lines": ["this is far too much text to read in one second"]}]
    assert any("cps" in w for w in lint_cues(fast)["warnings"])

    arabic = [{"start": 0.0, "end": 2.0, "lines": ["كلام عربي left over"]}]
    assert any("Arabic" in p for p in lint_cues(arabic)["problems"])

    honorific = [{"start": 0.0, "end": 2.0, "lines": ["the Prophet ﷺ said"]}]
    assert lint_cues(honorific)["problems"] == []


def test_lint_run_clean_and_coverage(tmp_path):
    run = _make_run(tmp_path)
    assemble(run)
    master = {"style": "", "terms": {"التوحيد": {"translit": "tawhid", "english": "oneness"}},
              "names": {}, "works": {}}
    r = lint_run(run, master)
    assert r["problems"] == []


def test_lint_run_glossary_drift(tmp_path):
    run = _make_run(tmp_path)
    assemble(run)
    master = {"style": "", "terms": {"العالمين": {"translit": "al-alamin", "english": "all creation"}},
              "names": {}, "works": {}}
    r = lint_run(run, master)  # Arabic contains العالمين but English says "the worlds"
    assert any("العالمين" in w for w in r["warnings"])
