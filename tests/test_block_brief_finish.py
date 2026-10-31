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


def _make_two_block_run(tmp_path):
    run = tmp_path / "sirah-01"
    work = run / "work"
    (work / "translated").mkdir(parents=True)
    segments = [
        {"i": 0, "w0": 0, "w1": 2, "text": "الحمد لله", "t0": 0.0, "t1": 2.0},
        {"i": 1, "w0": 2, "w1": 4, "text": "رب العالمين", "t0": 2.1, "t1": 4.0},
        {"i": 2, "w0": 4, "w1": 6, "text": "نتحدث عن السيرة", "t0": 4.5, "t1": 6.0},
        {"i": 3, "w0": 6, "w1": 8, "text": "في هذا الدرس", "t0": 6.1, "t1": 8.0},
    ]
    blocks = [{"n": 0, "s0": 0, "s1": 1, "context": ""},
              {"n": 1, "s0": 2, "s1": 3, "context": "رب العالمين"}]
    (work / "blocks.json").write_text(json.dumps(
        {"segments": segments, "blocks": blocks}, ensure_ascii=False), encoding="utf-8")
    (work / "translated" / "block_000.json").write_text(json.dumps({
        "block": 0,
        "sentences": [{"segs": [0, 1], "type": "prose",
                       "en": "Praise be to Allah, | Lord of the worlds",
                       "ref": None, "src": None, "flags": []}],
        "new_terms": [
            {"ar": "السيرة", "translit": "sirah",
             "english": "the Prophetic biography", "kind": "term"},
            {"ar": "التوحيد", "translit": "tawhid",
             "english": "the oneness of Allah", "kind": "term"}],
        "flags": []}, ensure_ascii=False), encoding="utf-8")
    return run


def _show(run, block, master=None):
    cmd = [sys.executable, "-m", "scripts.block_brief", "show", str(run), "--block", str(block)]
    if master:
        cmd += ["--master", str(master)]
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO))
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


def test_block_brief_lookahead(tmp_path):
    run = _make_two_block_run(tmp_path)
    first = _show(run, 0)
    assert "LOOKAHEAD" in first and "نتحدث عن السيرة" in first
    assert "LOOKAHEAD" not in _show(run, 1)      # last block has nothing to look ahead to


def test_block_brief_provisional_terms(tmp_path):
    run = _make_two_block_run(tmp_path)
    empty_master = tmp_path / "glossary.json"
    empty_master.write_text(json.dumps({"style": "", "terms": {}, "names": {}, "works": {}},
                                       ensure_ascii=False), encoding="utf-8")
    second = _show(run, 1, master=empty_master)
    # السيرة was coined by block 0 AND is spoken in block 1 → offered as provisional
    assert "PROVISIONAL" in second and "sirah" in second
    # التوحيد is not spoken in block 1 → left out
    assert "التوحيد" not in second
    # a block never sees its own new_terms echoed back as provisional
    assert "PROVISIONAL" not in _show(run, 0, master=empty_master)
    # a term the master already covers is not re-offered as provisional
    assert "PROVISIONAL" not in _show(run, 1)


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


def test_finish_lecture(tmp_path):
    run = _make_run(tmp_path)
    master = tmp_path / "glossary.json"
    master.write_text(json.dumps({"style": "", "terms": {}, "names": {}, "works": {}},
                                 ensure_ascii=False), encoding="utf-8")
    changelog = tmp_path / "glossary-changelog.md"
    proc = subprocess.run(
        [sys.executable, "-m", "scripts.finish_lecture", str(run),
         "--master", str(master), "--changelog", str(changelog)],
        capture_output=True, text=True, cwd=str(REPO))
    assert proc.returncode == 0, proc.stderr
    assert (run / "output" / "sirah-01.en.srt").exists()
    assert (run / "output" / "review.md").exists()
    assert (run / "output" / "bilingual.md").exists()
    assert "السيرة" in json.loads(master.read_text(encoding="utf-8"))["terms"]
    assert "problems: 0" in proc.stdout


def test_finish_lecture_italics_flag(tmp_path):
    run = _make_run(tmp_path)
    bf = run / "work" / "translated" / "block_000.json"
    payload = json.loads(bf.read_text(encoding="utf-8"))
    payload["sentences"][0].update(type="quran", ref="1:2", src="dataset")
    bf.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    master = tmp_path / "glossary.json"
    master.write_text(json.dumps({"style": "", "terms": {}, "names": {}, "works": {}},
                                 ensure_ascii=False), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, "-m", "scripts.finish_lecture", str(run), "--italics",
         "--master", str(master), "--changelog", str(tmp_path / "changelog.md")],
        capture_output=True, text=True, cwd=str(REPO))
    assert proc.returncode == 0, proc.stderr
    assert "<i>" in (run / "output" / "sirah-01.en.srt").read_text(encoding="utf-8")


def test_sync_editor_outputs(tmp_path):
    from scripts.finish_lecture import sync_editor_outputs
    run = _make_run(tmp_path)
    (run / "output").mkdir()
    (run / "output" / "sirah-01.en.srt").write_text("1\n", encoding="utf-8")
    (run / "output" / "bilingual.md").write_text("# b\n", encoding="utf-8")

    editor = tmp_path / "editor"
    editor.mkdir()
    sync_editor_outputs(run, REPO / "data" / "glossary.json", editor_dir=editor)
    assert (editor / "glossary.json").exists()
    assert (editor / "sirah-01.en.srt").exists()
    assert (editor / "bilingual.md").exists()

    guarded = tmp_path / "editor2"
    guarded.mkdir()
    sync_editor_outputs(run, tmp_path / "not-the-master.json", editor_dir=guarded)
    assert list(guarded.iterdir()) == []          # temp master → never clobber editor copies
