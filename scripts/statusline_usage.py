#!/usr/bin/env python3
"""Claude Code statusline: print a usage line and tee rate-limit state to a snapshot file.

Installed by copying to ~/.claude/statusline_usage.py — standalone, stdlib only, no repo imports.
Reads the statusline JSON payload from stdin. Never exits nonzero and always prints SOMETHING:
a broken statusline nags on every render. The snapshot is what scripts/run_status.py --gate reads.
"""
import json
import os
import sys
import tempfile
import time

DEFAULT_SNAPSHOT = os.path.expanduser("~/.claude/usage-snapshot.json")
# Keys must stay in sync with WINDOWS in scripts/run_status.py (labels differ; keys don't).
WINDOWS = (("five_hour", "session"), ("seven_day", "week"))


def render(data, now=None):
    """Return (statusline_text, snapshot_dict) — snapshot is None if the payload has no windows."""
    now = int(time.time()) if now is None else int(now)
    model = (data.get("model") or {}).get("display_name") or "claude"
    rl = data.get("rate_limits") or {}
    parts = [model]
    snap = {"written_at": now}
    for key, label in WINDOWS:
        win = rl.get(key) or {}
        pct = win.get("used_percentage")
        if pct is None:
            continue
        snap[key] = {"used_percentage": pct, "resets_at": win.get("resets_at")}
        parts.append("%s %d%%" % (label, round(pct)))
    resets = (rl.get("five_hour") or {}).get("resets_at")
    if resets:
        parts.append("resets %s" % time.strftime("%H:%M", time.localtime(resets)))
    has_windows = any(key in snap for key, _ in WINDOWS)
    return " · ".join(parts), (snap if has_windows else None)


def write_snapshot(snap, path):
    # atomic: temp file in the target's own directory, then rename over
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path) or ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(snap, f)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def main():
    try:
        # render() is inside the guard too: valid JSON of an unexpected shape
        # (e.g. a bare int, or a non-dict "model") must not break the statusline
        line, snap = render(json.load(sys.stdin))
    except Exception:
        print("claude")
        return
    if snap is not None:
        path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SNAPSHOT
        try:
            write_snapshot(snap, path)
        except Exception:
            pass  # the line must still print; the snapshot is best-effort
    print(line)


if __name__ == "__main__":
    main()
