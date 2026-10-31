import json
import subprocess
import sys

from scripts.run_status import chunk_state, gate_verdict


def _work(tmp_path, n_blocks, done):
    work = tmp_path / "work"
    (work / "translated").mkdir(parents=True)
    blocks = [{"n": i, "s0": i, "s1": i, "context": ""} for i in range(n_blocks)]
    (work / "blocks.json").write_text(json.dumps({"segments": [], "blocks": blocks}))
    for i in done:
        (work / "translated" / ("block_%03d.json" % i)).write_text("{}\n")
    return str(work)


def test_chunk_state_partial(tmp_path):
    assert chunk_state(_work(tmp_path, 4, done=[0, 2])) == {
        "total": 4, "done": [0, 2], "missing": [1, 3]}


def test_chunk_state_complete(tmp_path):
    state = chunk_state(_work(tmp_path, 2, done=[0, 1]))
    assert state["missing"] == [] and state["done"] == [0, 1]


def test_chunk_state_nothing_translated_yet(tmp_path):
    state = chunk_state(_work(tmp_path, 3, done=[]))
    assert state["done"] == [] and state["missing"] == [0, 1, 2]


def test_chunk_state_empty_file_counts_as_missing(tmp_path):
    work = _work(tmp_path, 2, done=[0])
    (tmp_path / "work" / "translated" / "block_001.json").write_text("")
    assert chunk_state(work)["missing"] == [1]


def test_chunk_state_not_chunked(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    assert chunk_state(str(work)) == {"not_chunked": True}


NOW = 1_000_000.0


def _snap(tmp_path, body):
    path = tmp_path / "usage-snapshot.json"
    path.write_text(body if isinstance(body, str) else json.dumps(body))
    return str(path)


def _fresh(five=50.0, seven=10.0):
    return {"written_at": NOW - 60,
            "five_hour": {"used_percentage": five, "resets_at": 1_003_600},
            "seven_day": {"used_percentage": seven, "resets_at": 1_600_000}}


def test_gate_proceed_under_threshold(tmp_path):
    v = gate_verdict(_snap(tmp_path, _fresh()), 90, now=NOW)
    assert v.startswith("PROCEED (session (5-hour) 50%, weekly 10%")


def test_gate_pause_on_session_window(tmp_path):
    v = gate_verdict(_snap(tmp_path, _fresh(five=93.0)), 90, now=NOW)
    assert v.startswith("PAUSE (session (5-hour) window at 93%")
    assert "resets" in v


def test_gate_pause_on_weekly_window(tmp_path):
    v = gate_verdict(_snap(tmp_path, _fresh(seven=97.0)), 90, now=NOW)
    assert v.startswith("PAUSE (weekly window at 97%")


def test_gate_session_named_before_weekly_when_both_trip(tmp_path):
    v = gate_verdict(_snap(tmp_path, _fresh(five=95.0, seven=99.0)), 90, now=NOW)
    assert v.startswith("PAUSE (session (5-hour) window at 95%")


def test_gate_threshold_is_inclusive(tmp_path):
    v = gate_verdict(_snap(tmp_path, _fresh(five=90.0)), 90, now=NOW)
    assert v.startswith("PAUSE")


def test_gate_missing_snapshot_fails_open(tmp_path):
    v = gate_verdict(str(tmp_path / "nope.json"), 90, now=NOW)
    assert v.startswith("PROCEED (gate degraded: no usage snapshot")


def test_gate_malformed_snapshot_fails_open(tmp_path):
    v = gate_verdict(_snap(tmp_path, "{broken"), 90, now=NOW)
    assert v.startswith("PROCEED (gate degraded:") and "unreadable" in v


def test_gate_bad_written_at_fails_open(tmp_path):
    v = gate_verdict(_snap(tmp_path, {"written_at": "yesterday"}), 90, now=NOW)
    assert v.startswith("PROCEED (gate degraded:")


def test_gate_stale_snapshot_fails_open(tmp_path):
    snap = _fresh()
    snap["written_at"] = NOW - 3600
    v = gate_verdict(_snap(tmp_path, snap), 90, now=NOW)
    assert v.startswith("PROCEED (gate degraded:") and "minutes old" in v


def test_gate_snapshot_without_windows_degrades(tmp_path):
    v = gate_verdict(_snap(tmp_path, {"written_at": NOW - 5}), 90, now=NOW)
    assert v.startswith("PROCEED (gate degraded: snapshot has no usage windows")


def test_gate_string_percentage_fails_open(tmp_path):
    snap = _fresh()
    snap["five_hour"]["used_percentage"] = "80"
    v = gate_verdict(_snap(tmp_path, snap), 90, now=NOW)
    assert v.startswith("PROCEED (gate degraded: unexpected")


def test_gate_non_dict_window_fails_open(tmp_path):
    snap = _fresh()
    snap["five_hour"] = [80]
    v = gate_verdict(_snap(tmp_path, snap), 90, now=NOW)
    assert v.startswith("PROCEED (gate degraded: unexpected")


def test_gate_single_window_names_only_it(tmp_path):
    snap = {"written_at": NOW - 60,
            "five_hour": {"used_percentage": 40.0, "resets_at": 1_003_600}}
    v = gate_verdict(_snap(tmp_path, snap), 90, now=NOW)
    assert v.startswith("PROCEED (session (5-hour) 40%")
    assert "weekly" not in v


def test_gate_pause_null_resets_at_says_unknown(tmp_path):
    snap = _fresh(five=95.0)
    snap["five_hour"]["resets_at"] = None
    v = gate_verdict(_snap(tmp_path, snap), 90, now=NOW)
    assert v.startswith("PAUSE") and "resets unknown" in v


def test_cli_smoke_state_plus_degraded_gate(tmp_path):
    work = _work(tmp_path, 3, done=[0])
    proc = subprocess.run(
        [sys.executable, "-m", "scripts.run_status", work,
         "--gate", "--snapshot", str(tmp_path / "none.json")],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0
    assert "blocks: 3 total, 1 done, 2 missing" in proc.stdout
    assert "missing: block_001, block_002" in proc.stdout
    assert "gate: PROCEED (gate degraded" in proc.stdout


def test_cli_not_chunked_exits_zero(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    proc = subprocess.run(
        [sys.executable, "-m", "scripts.run_status", str(work)],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0
    assert "not ingested yet" in proc.stdout


def test_cli_bad_work_dir_exits_2(tmp_path):
    proc = subprocess.run(
        [sys.executable, "-m", "scripts.run_status", str(tmp_path / "nope")],
        capture_output=True, text=True,
    )
    assert proc.returncode == 2


def test_cli_corrupt_blocks_json_exits_2(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    (work / "blocks.json").write_text("{ broken json")
    proc = subprocess.run(
        [sys.executable, "-m", "scripts.run_status", str(work)],
        capture_output=True, text=True,
    )
    assert proc.returncode == 2
    assert "unreadable blocks.json" in proc.stderr


def test_cli_non_dict_blocks_json_exits_2(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    (work / "blocks.json").write_text("42")
    proc = subprocess.run(
        [sys.executable, "-m", "scripts.run_status", str(work)],
        capture_output=True, text=True,
    )
    assert proc.returncode == 2
    assert "unreadable blocks.json" in proc.stderr
