"""Integration test binding the statusline writer to the run_status gate reader.

Exercises the real seam: statusline_usage.render()/write_snapshot() produce the file that
run_status.gate_verdict() reads. The two modules duplicate the snapshot shape (statusline can't
import from the repo — see the WINDOWS comments in both files), so an isolated-suite-only
regression in either module's shape would silently pass while the gate degrades (fails open).
This test pins the contract at the round-trip level.
"""
from scripts.statusline_usage import render, write_snapshot
from scripts.run_status import gate_verdict

NOW = 1_000_000.0

SAMPLE = {
    "model": {"display_name": "Fable"},
    "rate_limits": {
        "five_hour": {"used_percentage": 42.5, "resets_at": NOW + 3600},
        "seven_day": {"used_percentage": 13.0, "resets_at": NOW + 600_000},
    },
}


def test_roundtrip_proceed_under_threshold(tmp_path):
    line, snap = render(SAMPLE, now=NOW - 60)
    path = str(tmp_path / "snap.json")
    write_snapshot(snap, path)

    verdict = gate_verdict(path, 90, now=NOW)

    assert verdict.startswith("PROCEED")
    assert "gate degraded" not in verdict


def test_roundtrip_pause_on_session_window(tmp_path):
    payload = {
        "model": {"display_name": "Fable"},
        "rate_limits": {
            "five_hour": {"used_percentage": 95.0, "resets_at": NOW + 3600},
            "seven_day": {"used_percentage": 13.0, "resets_at": NOW + 600_000},
        },
    }
    line, snap = render(payload, now=NOW - 60)
    path = str(tmp_path / "snap.json")
    write_snapshot(snap, path)

    verdict = gate_verdict(path, 90, now=NOW)

    assert verdict.startswith("PAUSE")
    assert "session (5-hour)" in verdict
