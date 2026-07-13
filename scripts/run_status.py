"""Run state + usage gate for a translation run.

    python -m scripts.run_status <book>/work [--gate] [--threshold 90]
                                 [--snapshot PATH] [--now EPOCH]

Prints chunk state (done/missing vs chunks.json). With --gate, also reads the statusline usage
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


def chunk_state(work_dir):
    """Diff blocks.json against translated/block_NNN.json.

    Returns {"total", "done", "missing"} (0-based block numbers), or {"not_chunked": True}
    when blocks.json does not exist. A 0-byte block file counts as missing. The "size > 0 = done"
    heuristic cannot detect a truncated/partial block file; acceptable because subagents write
    the complete file before their final self-check."""
    blocks_path = os.path.join(work_dir, "blocks.json")
    if not os.path.exists(blocks_path):
        return {"not_chunked": True}
    with open(blocks_path) as f:
        blocks = json.load(f)["blocks"]
    done, missing = [], []
    for i in range(len(blocks)):
        path = os.path.join(work_dir, "translated", "block_%03d.json" % i)
        (done if os.path.exists(path) and os.path.getsize(path) > 0 else missing).append(i)
    return {"total": len(blocks), "done": done, "missing": missing}


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
    ap.add_argument("work_dir", help="the run's work directory (contains blocks.json)")
    ap.add_argument("--gate", action="store_true", help="also print a PROCEED/PAUSE verdict")
    ap.add_argument("--threshold", type=float, default=90.0)
    ap.add_argument("--snapshot", default=DEFAULT_SNAPSHOT)
    ap.add_argument("--now", type=float, default=None, help="epoch override for tests")
    args = ap.parse_args()

    if not os.path.isdir(args.work_dir):
        ap.exit(2, "run_status: work dir not found: %s\n" % args.work_dir)

    try:
        state = chunk_state(args.work_dir)
    except (json.JSONDecodeError, ValueError, OSError, TypeError, KeyError):
        ap.exit(2, "run_status: unreadable blocks.json in %s\n" % args.work_dir)
    if state.get("not_chunked"):
        print("not ingested yet — no blocks.json in %s; restart from step 1 (ingest)"
              % args.work_dir)
    else:
        print("blocks: %d total, %d done, %d missing"
              % (state["total"], len(state["done"]), len(state["missing"])))
        if state["missing"]:
            print("missing: %s" % ", ".join("block_%03d" % i for i in state["missing"]))
        print("state: %s" % json.dumps(state))

    if args.gate:
        print("gate: %s" % gate_verdict(args.snapshot, args.threshold, args.now))


if __name__ == "__main__":
    main()
