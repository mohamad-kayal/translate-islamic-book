"""Run state + usage gate for a translation run.

    python -m scripts.run_status <run>/work [--gate] [--threshold 90]
                                 [--snapshot PATH] [--now EPOCH]

Prints unit state: a book's chunks (chunks.json) or a lecture's blocks (blocks.json). With --gate, also reads the statusline usage
snapshot and prints a PROCEED/PAUSE verdict. The gate FAILS OPEN — a missing, malformed, or stale
snapshot degrades to PROCEED with the reason stated; resumability is the net underneath. Exits 0
in all cases except an unusable work dir (exit 2): verdicts are text for the orchestrator to
read, not shell logic.
"""
import argparse
import json
import os
import time


DEFAULT_SNAPSHOT = os.path.expanduser("~/.claude/usage-snapshot.json")
STALE_SECONDS = 900
# Keys must stay in sync with WINDOWS in scripts/statusline_usage.py (labels differ; keys don't).
WINDOWS = (("five_hour", "session (5-hour)"), ("seven_day", "weekly"))


# plan file, unit name, translated-file pattern, first unit number
_LAYOUTS = (("chunks.json", "chunk", "chunk_%04d.md", 1),
            ("blocks.json", "block", "block_%03d.json", 0))


def _layout(work_dir):
    for layout in _LAYOUTS:
        if os.path.exists(os.path.join(work_dir, layout[0])):
            return layout
    return None


def chunk_state(work_dir):
    """Diff the run's plan against its translated/ files.

    Returns {"total", "done", "missing"} (unit numbers: 1-based chunks, 0-based blocks), or
    {"not_chunked": True} when no plan exists. A 0-byte file counts as missing. The
    "size > 0 = done" heuristic cannot detect a truncated file; acceptable because translators
    write the complete file before their final self-check."""
    layout = _layout(work_dir)
    if layout is None:
        return {"not_chunked": True}
    plan, _, pattern, first = layout
    with open(os.path.join(work_dir, plan)) as f:
        data = json.load(f)
    units = data["blocks"] if plan == "blocks.json" else data
    done, missing = [], []
    for i in range(first, first + len(units)):
        path = os.path.join(work_dir, "translated", pattern % i)
        (done if os.path.exists(path) and os.path.getsize(path) > 0 else missing).append(i)
    return {"total": len(units), "done": done, "missing": missing}


def gate_verdict(snapshot_path, threshold, now=None):
    """PROCEED/PAUSE from the usage snapshot. Fails open, always stating why."""
    now = time.time() if now is None else now
    try:
        with open(snapshot_path) as f:
            snap = json.load(f)
        written = float(snap["written_at"])
    except FileNotFoundError:
        return ("PROCEED (gate degraded: no usage snapshot at %s — "
                "is the statusline installed?)" % snapshot_path)
    except (OSError, ValueError, KeyError, TypeError):
        return "PROCEED (gate degraded: unreadable usage snapshot at %s)" % snapshot_path
    try:
        age = now - written
        if age > STALE_SECONDS:
            return "PROCEED (gate degraded: usage snapshot is %d minutes old)" % (age // 60)
        seen = []
        for key, label in WINDOWS:
            win = snap.get(key) or {}
            pct = win.get("used_percentage")
            if pct is None:
                continue
            if pct >= threshold:
                resets = win.get("resets_at")
                when = (time.strftime("%a %H:%M", time.localtime(resets))
                        if resets else "unknown")
                return ("PAUSE (%s window at %d%% >= threshold %d%% — resets %s)"
                        % (label, round(pct), threshold, when))
            seen.append("%s %d%%" % (label, round(pct)))
        if not seen:
            return "PROCEED (gate degraded: snapshot has no usage windows)"
        return "PROCEED (%s — under threshold %d%%)" % (", ".join(seen), threshold)
    except Exception:
        return ("PROCEED (gate degraded: unexpected usage snapshot content at %s)"
                % snapshot_path)


def main():
    ap = argparse.ArgumentParser(
        description="Run state + usage gate for a translation run (see module docstring).")
    ap.add_argument("work_dir", help="the run's work directory (contains chunks.json or blocks.json)")
    ap.add_argument("--gate", action="store_true", help="also print a PROCEED/PAUSE verdict")
    ap.add_argument("--threshold", type=float, default=90.0)
    ap.add_argument("--snapshot", default=DEFAULT_SNAPSHOT)
    ap.add_argument("--now", type=float, default=None, help="epoch override for tests")
    args = ap.parse_args()

    if not os.path.isdir(args.work_dir):
        ap.exit(2, "run_status: work dir not found: %s\n" % args.work_dir)

    layout = _layout(args.work_dir)
    try:
        state = chunk_state(args.work_dir)
    except (json.JSONDecodeError, ValueError, OSError, TypeError, KeyError):
        ap.exit(2, "run_status: unreadable %s in %s\n" % (layout[0], args.work_dir))
    if state.get("not_chunked"):
        print("not ingested yet — no chunks.json or blocks.json in %s; restart from step 1 "
              "(ingest)" % args.work_dir)
    else:
        _, unit, pattern, _ = layout
        print("%ss: %d total, %d done, %d missing"
              % (unit, state["total"], len(state["done"]), len(state["missing"])))
        if state["missing"]:
            print("missing: %s" % ", ".join(pattern.split(".")[0] % i for i in state["missing"]))
        print("state: %s" % json.dumps(state))

    if args.gate:
        print("gate: %s" % gate_verdict(args.snapshot, args.threshold, args.now))


if __name__ == "__main__":
    main()
