import json
import pathlib
import subprocess
import sys

import pytest

from subs.report import write_bilingual, write_review

REPO = pathlib.Path(__file__).parent.parent
SAMPLE = pathlib.Path(__file__).parent / "fixtures" / "sample_head.srt"


def _make_run(tmp_path):
    run = tmp_path / "sirah-01"
    work = run / "work"
    (work / "translated").mkdir(parents=True)
    segments = [
        {"i": 0, "w0": 0, "w1": 2, "text": "الحمد لله", "t0": 61.0, "t1": 63.0},
        {"i": 1, "w0": 2, "w1": 4, "text": "رب العالمين", "t0": 63.1, "t1": 65.0},
    ]
    (work / "blocks.json").write_text(json.dumps(
        {"segments": segments, "blocks": [{"n": 0, "s0": 0, "s1": 1, "context": ""}]},
        ensure_ascii=False), encoding="utf-8")
    (work / "translated" / "block_000.json").write_text(json.dumps({
        "block": 0,
        "sentences": [{"segs": [0, 1], "type": "quran", "en": "Praise be to Allah, Lord of the worlds",
                       "ref": "1:2", "src": "dataset", "flags": ["partial verse"]}],
        "new_terms": [], "flags": []}, ensure_ascii=False), encoding="utf-8")
    return run


def test_bilingual_stacks_time_arabic_english(tmp_path):
    run = _make_run(tmp_path)
    write_bilingual(run)
    text = (run / "output" / "bilingual.md").read_text(encoding="utf-8")
    assert "[01:01]" in text
    assert "الحمد لله رب العالمين" in text
    assert "Praise be to Allah" in text


def test_review_sections(tmp_path):
    run = _make_run(tmp_path)
    stats = {"sentences": 1, "quran": 1, "hadith": 0, "fallbacks": 0, "cues": 1,
             "warnings": ["cue 1: reading speed 21.0 cps"], "output": "x"}
    harvest_result = {"added": {"السيرة": {"section": "terms",
                                            "value": {"translit": "sirah", "english": "biography"}}},
                      "conflicts": [{"section": "terms", "ar": "التوحيد", "existing_key": "التوحيد",
                                     "master": {"translit": "tawhid", "english": "oneness"},
                                     "proposed": {"translit": "tawhid", "english": "monotheism"}}]}
    lint_result = {"problems": [], "warnings": ["glossary drift: x"]}
    write_review(run, stats, harvest_result, lint_result)
    text = (run / "output" / "review.md").read_text(encoding="utf-8")
    assert "1:2" in text                # scripture listed with ref
    assert "partial verse" in text      # sentence flag
    assert "السيرة" in text             # glossary growth
    assert "التوحيد" in text            # conflict pending
    assert "21.0 cps" in text           # warnings carried


def test_ingest_cli_on_real_sample(tmp_path):
    run = tmp_path / "sample"
    proc = subprocess.run(
        [sys.executable, "-m", "scripts.ingest_video", str(SAMPLE), "--run", str(run)],
        capture_output=True, text=True, cwd=str(REPO))
    assert proc.returncode == 0, proc.stderr
    timeline = json.loads((run / "work" / "timeline.json").read_text(encoding="utf-8"))
    data = json.loads((run / "work" / "blocks.json").read_text(encoding="utf-8"))
    assert timeline["kind"] == "srt"
    assert len(timeline["words"]) > 100
    assert data["blocks"][0]["s0"] == 0
    assert "words" in proc.stdout and "blocks" in proc.stdout


def test_glossary_cli_subset(tmp_path):
    run = _make_run(tmp_path)
    proc = subprocess.run(
        [sys.executable, "-m", "scripts.glossary", "subset", str(run), "--block", "0"],
        capture_output=True, text=True, cwd=str(REPO))
    assert proc.returncode == 0, proc.stderr
    sub = json.loads(proc.stdout)
    assert "style" in sub and "names" in sub


WORD_TIMED = '{"events": [{"tStartMs": 0, "segs": [{"utf8": "a"}, {"utf8": "b", "tOffsetMs": 40}]}]}'
LINE_TIMED = '{"events": [{"tStartMs": 0, "dDurationMs": 900, "segs": [{"utf8": "a b c"}]}]}'


def _fake_ytdlp(monkeypatch, per_client):
    """Stand in for yt-dlp: each client writes its own track, or nothing."""
    import scripts.ingest_video as iv
    calls = []

    def run(cmd, env=None):
        client = next((a.split("=")[1] for a in cmd if "player_client" in a), None)
        calls.append(client)
        if per_client.get(client):
            pathlib.Path(cmd[cmd.index("-o") + 1] + ".ar.json3").write_text(per_client[client])
    monkeypatch.setattr(iv.subprocess, "run", run)
    return iv, calls


def test_fetch_stops_at_the_first_client_with_word_timing(tmp_path, monkeypatch):
    iv, calls = _fake_ytdlp(monkeypatch, {None: WORD_TIMED, "android": LINE_TIMED})
    assert iv.fetch_json3("u", tmp_path).read_text() == WORD_TIMED
    assert calls == [None]


def test_fetch_tries_the_next_client_for_word_timing(tmp_path, monkeypatch):
    iv, calls = _fake_ytdlp(monkeypatch, {None: LINE_TIMED, "android": WORD_TIMED})
    assert iv.fetch_json3("u", tmp_path).read_text() == WORD_TIMED
    assert calls == [None, "android"]


def test_fetch_settles_for_line_timing_when_nothing_better_exists(tmp_path, monkeypatch):
    iv, _ = _fake_ytdlp(monkeypatch, {None: None, "android": LINE_TIMED})
    assert iv.fetch_json3("u", tmp_path).read_text() == LINE_TIMED


def test_fetch_fails_loudly_when_no_client_has_captions(tmp_path, monkeypatch):
    iv, _ = _fake_ytdlp(monkeypatch, {})
    with pytest.raises(SystemExit):
        iv.fetch_json3("u", tmp_path)
