import json
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).parent.parent


def _make_run(tmp_path, with_translation=True):
    run = tmp_path / "sirah-01"
    work = run / "work"
    (work / "translated").mkdir(parents=True)
    segments = [
        {"i": 0, "w0": 0, "w1": 2, "text": "الحمد لله", "t0": 0.0, "t1": 2.0},
        {"i": 1, "w0": 2, "w1": 4, "text": "رب العالمين", "t0": 2.1, "t1": 4.0},
    ]
    (work / "blocks.json").write_text(json.dumps(
        {"segments": segments, "blocks": [{"n": 0, "s0": 0, "s1": 1, "context": "سياق سابق"}]},
        ensure_ascii=False), encoding="utf-8")
    if with_translation:
        (work / "translated" / "block_000.json").write_text(json.dumps({
            "block": 0,
            "sentences": [{"segs": [0, 1], "type": "prose",
                           "en": "Praise be to Allah, | Lord of the worlds",
                           "ref": None, "src": None, "flags": []}],
            "new_terms": [{"ar": "السيرة", "translit": "sirah",
                           "english": "the Prophetic biography", "kind": "term"}],
            "flags": []}, ensure_ascii=False), encoding="utf-8")
    return run


def test_block_brief_show(tmp_path):
    run = _make_run(tmp_path, with_translation=False)
    proc = subprocess.run(
        [sys.executable, "-m", "scripts.block_brief", "show", str(run), "--block", "0"],
        capture_output=True, text=True, cwd=str(REPO))
    assert proc.returncode == 0, proc.stderr
    assert "[0|2.0s] الحمد لله" in proc.stdout
    assert "[1|1.9s] رب العالمين" in proc.stdout
    assert "سياق سابق" in proc.stdout          # context shown
    assert "GLOSSARY" in proc.stdout


def test_block_brief_check_ok_and_bad(tmp_path):
    run = _make_run(tmp_path)
    proc = subprocess.run(
        [sys.executable, "-m", "scripts.block_brief", "check", str(run), "--block", "0"],
        capture_output=True, text=True, cwd=str(REPO))
    assert proc.returncode == 0, proc.stderr
    assert "OK" in proc.stdout

    bad = json.loads((run / "work" / "translated" / "block_000.json").read_text(encoding="utf-8"))
    bad["sentences"][0]["segs"] = [0, 0]  # leaves segment 1 uncovered
    (run / "work" / "translated" / "block_000.json").write_text(
        json.dumps(bad, ensure_ascii=False), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, "-m", "scripts.block_brief", "check", str(run), "--block", "0"],
        capture_output=True, text=True, cwd=str(REPO))
    assert proc.returncode == 1
    assert "uncovered" in proc.stdout


def test_finish_run(tmp_path):
    run = _make_run(tmp_path)
    master = tmp_path / "glossary.json"
    master.write_text(json.dumps({"style": "", "terms": {}, "names": {}, "works": {}},
                                 ensure_ascii=False), encoding="utf-8")
    changelog = tmp_path / "glossary-changelog.md"
    proc = subprocess.run(
        [sys.executable, "-m", "scripts.finish_run", str(run),
         "--master", str(master), "--changelog", str(changelog)],
        capture_output=True, text=True, cwd=str(REPO))
    assert proc.returncode == 0, proc.stderr
    assert (run / "output" / "sirah-01.en.srt").exists()
    assert (run / "output" / "review.md").exists()
    assert (run / "output" / "bilingual.md").exists()
    assert "السيرة" in json.loads(master.read_text(encoding="utf-8"))["terms"]
    assert "problems: 0" in proc.stdout
