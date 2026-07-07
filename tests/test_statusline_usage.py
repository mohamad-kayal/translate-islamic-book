import json
import subprocess
import sys

from scripts.statusline_usage import render, write_snapshot

SAMPLE = {
    "model": {"display_name": "Fable"},
    "rate_limits": {
        "five_hour": {"used_percentage": 42.5, "resets_at": 1751912345},
        "seven_day": {"used_percentage": 13.0, "resets_at": 1752300000},
    },
}


def test_render_line_and_snapshot():
    line, snap = render(SAMPLE, now=1751900000)
    # resets time is local-timezone formatted, so assert only the prefix
    assert line.startswith("Fable · session 42% · week 13% · resets ")
    assert snap["written_at"] == 1751900000
    assert snap["five_hour"] == {"used_percentage": 42.5, "resets_at": 1751912345}
    assert snap["seven_day"] == {"used_percentage": 13.0, "resets_at": 1752300000}


def test_render_without_rate_limits_gives_line_but_no_snapshot():
    line, snap = render({"model": {"display_name": "Fable"}}, now=0)
    assert line == "Fable"
    assert snap is None


def test_render_single_window_only():
    payload = {"model": {}, "rate_limits": {"five_hour": {"used_percentage": 9.0}}}
    line, snap = render(payload, now=5)
    assert line == "claude · session 9%"
    assert "seven_day" not in snap
    assert snap["five_hour"] == {"used_percentage": 9.0, "resets_at": None}


def test_write_snapshot_is_atomic_and_leaves_no_temp(tmp_path):
    path = tmp_path / "usage-snapshot.json"
    write_snapshot({"written_at": 1}, str(path))
    assert json.loads(path.read_text()) == {"written_at": 1}
    assert list(tmp_path.iterdir()) == [path]


def test_cli_garbage_stdin_prints_fallback_and_exits_zero(tmp_path):
    proc = subprocess.run(
        [sys.executable, "scripts/statusline_usage.py", str(tmp_path / "snap.json")],
        input="not json", capture_output=True, text=True,
    )
    assert proc.returncode == 0
    assert proc.stdout.strip() == "claude"
    assert not (tmp_path / "snap.json").exists()


def test_cli_valid_json_wrong_shape_prints_fallback_and_exits_zero(tmp_path):
    # valid JSON, unexpected shapes: bare non-dict, non-dict model, non-dict rate_limits
    for payload in ("42", "null", "[]", '{"model": "not-a-dict"}',
                    '{"model": {}, "rate_limits": "not-a-dict"}'):
        snap_path = tmp_path / "snap.json"
        proc = subprocess.run(
            [sys.executable, "scripts/statusline_usage.py", str(snap_path)],
            input=payload, capture_output=True, text=True,
        )
        assert proc.returncode == 0, "exit %d for payload %s" % (proc.returncode, payload)
        assert proc.stdout.strip() == "claude", "stdout %r for payload %s" % (proc.stdout, payload)
        assert not snap_path.exists(), "snapshot written for payload %s" % payload


def test_cli_writes_snapshot(tmp_path):
    snap_path = tmp_path / "snap.json"
    proc = subprocess.run(
        [sys.executable, "scripts/statusline_usage.py", str(snap_path)],
        input=json.dumps(SAMPLE), capture_output=True, text=True,
    )
    assert proc.returncode == 0
    assert "session 42%" in proc.stdout
    assert json.loads(snap_path.read_text())["five_hour"]["used_percentage"] == 42.5
