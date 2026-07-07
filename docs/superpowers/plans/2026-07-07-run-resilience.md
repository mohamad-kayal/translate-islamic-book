# Run Resilience Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A translation run pauses cleanly before the subscription usage wall and resumes with one sentence — it can never lose more than the in-flight wave.

**Architecture:** A statusline script tees Claude Code's `rate_limits` JSON to `~/.claude/usage-snapshot.json` on every render. A new `scripts/run_status.py` diffs `chunks.json` against `translated/chunk_NNNN.md` (resume state) and, with `--gate`, reads the snapshot and prints a PROCEED/PAUSE verdict. SKILL.md gains the gate call before every dispatch wave, a RESUME.md checklist, and a resume procedure. Spec: `docs/superpowers/specs/2026-07-07-run-resilience-design.md`.

**Tech Stack:** Python 3 stdlib only (json/os/time/argparse/tempfile), pytest.

## Global Constraints

- Stdlib only — no new dependencies (house rule).
- Run tests from the repo root: `.venv/bin/python -m pytest tests/<file> -v`.
- The gate **fails open**: missing/malformed/stale snapshot → `PROCEED (gate degraded: <reason>)`.
- `run_status` exits 0 in all cases except an unusable work dir path (exit 2). Verdicts are text for the orchestrator, not shell logic.
- Defaults (from spec): snapshot `~/.claude/usage-snapshot.json`; threshold `90.0`; stale after `900` seconds; both `five_hour` and `seven_day` windows gate, `five_hour` named first when both trip.
- `chunks.json` is a JSON **list**; chunk numbers are 1-based; chunk i ↔ `translated/chunk_%04d.md`; an empty (0-byte) chunk file counts as missing.
- Match existing test style: plain pytest functions, small `_helpers`, `%`-formatting.
- Commit to `main` directly (project convention). NEVER `git push`.
- The statusline script must be standalone (no repo imports) — it gets copied to `~/.claude/`.

---

### Task 1: `scripts/statusline_usage.py` — snapshot writer + statusline

**Files:**
- Create: `scripts/statusline_usage.py`
- Test: `tests/test_statusline_usage.py`

**Interfaces:**
- Consumes: nothing from this repo (standalone by design).
- Produces: `render(data: dict, now: int|None = None) -> (str, dict|None)` — statusline text and snapshot dict (or `None` when the payload has no usage windows); `write_snapshot(snap: dict, path: str) -> None` (atomic); CLI: `python3 scripts/statusline_usage.py [SNAPSHOT_PATH]` reading statusline JSON on stdin. Snapshot shape (Task 3's gate reads it): `{"written_at": int, "five_hour": {"used_percentage": float, "resets_at": int|None}, "seven_day": {...}}` — a window key is present only if the payload had it.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_statusline_usage.py
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


def test_cli_writes_snapshot(tmp_path):
    snap_path = tmp_path / "snap.json"
    proc = subprocess.run(
        [sys.executable, "scripts/statusline_usage.py", str(snap_path)],
        input=json.dumps(SAMPLE), capture_output=True, text=True,
    )
    assert proc.returncode == 0
    assert "session 42%" in proc.stdout
    assert json.loads(snap_path.read_text())["five_hour"]["used_percentage"] == 42.5
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_statusline_usage.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.statusline_usage'`

- [ ] **Step 3: Write the implementation**

```python
# scripts/statusline_usage.py
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
        data = json.load(sys.stdin)
    except Exception:
        print("claude")
        return
    line, snap = render(data)
    if snap is not None:
        path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SNAPSHOT
        try:
            write_snapshot(snap, path)
        except Exception:
            pass  # the line must still print; the snapshot is best-effort
    print(line)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_statusline_usage.py -v`
Expected: 6 passed

- [ ] **Step 5: Run the full suite (no regressions)**

Run: `.venv/bin/python -m pytest -m "not integration"`
Expected: all pass (100 passed before this plan + 6 new)

- [ ] **Step 6: Commit**

```bash
git add scripts/statusline_usage.py tests/test_statusline_usage.py
git commit -m "feat(resilience): statusline usage-snapshot writer"
```

---

### Task 2: `scripts/run_status.py` — chunk state diff

**Files:**
- Create: `scripts/run_status.py`
- Test: `tests/test_run_status.py`

**Interfaces:**
- Consumes: `<work>/chunks.json` (JSON list, as written by `scripts.ingest_book chunk`) and `<work>/translated/chunk_%04d.md` files.
- Produces: `chunk_state(work_dir: str) -> dict` — `{"total": int, "done": [int], "missing": [int]}`, or `{"not_chunked": True}` when `chunks.json` is absent. Task 3 adds `gate_verdict` and `main` to this same file.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_run_status.py
import json

from scripts.run_status import chunk_state


def _work(tmp_path, n_chunks, done):
    work = tmp_path / "work"
    (work / "translated").mkdir(parents=True)
    chunks = [{"sections": ["S%d" % i], "start_page": i, "end_page": i}
              for i in range(1, n_chunks + 1)]
    (work / "chunks.json").write_text(json.dumps(chunks))
    for i in done:
        (work / "translated" / ("chunk_%04d.md" % i)).write_text("# translated\n")
    return str(work)


def test_chunk_state_partial(tmp_path):
    assert chunk_state(_work(tmp_path, 4, done=[1, 3])) == {
        "total": 4, "done": [1, 3], "missing": [2, 4]}


def test_chunk_state_complete(tmp_path):
    state = chunk_state(_work(tmp_path, 2, done=[1, 2]))
    assert state["missing"] == [] and state["done"] == [1, 2]


def test_chunk_state_nothing_translated_yet(tmp_path):
    state = chunk_state(_work(tmp_path, 3, done=[]))
    assert state["done"] == [] and state["missing"] == [1, 2, 3]


def test_chunk_state_empty_file_counts_as_missing(tmp_path):
    work = _work(tmp_path, 2, done=[1])
    (tmp_path / "work" / "translated" / "chunk_0002.md").write_text("")
    assert chunk_state(work)["missing"] == [2]


def test_chunk_state_not_chunked(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    assert chunk_state(str(work)) == {"not_chunked": True}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_run_status.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.run_status'`

- [ ] **Step 3: Write the implementation**

```python
# scripts/run_status.py
"""Run state + usage gate for a translation run.

    python -m scripts.run_status <book>/work [--gate] [--threshold 90]
                                 [--snapshot PATH] [--now EPOCH]

Prints chunk state (done/missing vs chunks.json). With --gate, also reads the statusline usage
snapshot and prints a PROCEED/PAUSE verdict. The gate FAILS OPEN — a missing, malformed, or stale
snapshot degrades to PROCEED with the reason stated; resumability is the net underneath. Exits 0
in all cases except an unusable work dir (exit 2): verdicts are text for the orchestrator to
read, not shell logic.
"""
import json
import os


def chunk_state(work_dir):
    """Diff chunks.json against translated/chunk_NNNN.md.

    Returns {"total", "done", "missing"} (1-based chunk numbers), or {"not_chunked": True}
    when chunks.json does not exist. A 0-byte chunk file counts as missing."""
    chunks_path = os.path.join(work_dir, "chunks.json")
    if not os.path.exists(chunks_path):
        return {"not_chunked": True}
    with open(chunks_path) as f:
        chunks = json.load(f)
    done, missing = [], []
    for i in range(1, len(chunks) + 1):
        path = os.path.join(work_dir, "translated", "chunk_%04d.md" % i)
        (done if os.path.exists(path) and os.path.getsize(path) > 0 else missing).append(i)
    return {"total": len(chunks), "done": done, "missing": missing}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_run_status.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add scripts/run_status.py tests/test_run_status.py
git commit -m "feat(resilience): run_status chunk-state diff"
```

---

### Task 3: gate verdict + CLI in `scripts/run_status.py`

**Files:**
- Modify: `scripts/run_status.py` (append `gate_verdict`, `main`, constants)
- Test: `tests/test_run_status.py` (append gate + CLI tests)

**Interfaces:**
- Consumes: `chunk_state` from Task 2; the snapshot file shape from Task 1 (`written_at`, `five_hour`/`seven_day` with `used_percentage`/`resets_at`).
- Produces: `gate_verdict(snapshot_path: str, threshold: float, now: float|None = None) -> str` — starts with `"PROCEED"` or `"PAUSE"`; CLI `python -m scripts.run_status <work> [--gate] [--threshold] [--snapshot] [--now]`. SKILL.md (Task 5) tells the orchestrator to run exactly this.

- [ ] **Step 1: Append the failing tests**

```python
# append to tests/test_run_status.py
import subprocess
import sys

from scripts.run_status import gate_verdict

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


def test_cli_smoke_state_plus_degraded_gate(tmp_path):
    work = _work(tmp_path, 3, done=[1])
    proc = subprocess.run(
        [sys.executable, "-m", "scripts.run_status", work,
         "--gate", "--snapshot", str(tmp_path / "none.json")],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0
    assert "chunks: 3 total, 1 done, 2 missing" in proc.stdout
    assert "missing: chunk_0002, chunk_0003" in proc.stdout
    assert "gate: PROCEED (gate degraded" in proc.stdout


def test_cli_not_chunked_exits_zero(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    proc = subprocess.run(
        [sys.executable, "-m", "scripts.run_status", str(work)],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0
    assert "not chunked yet" in proc.stdout


def test_cli_bad_work_dir_exits_2(tmp_path):
    proc = subprocess.run(
        [sys.executable, "-m", "scripts.run_status", str(tmp_path / "nope")],
        capture_output=True, text=True,
    )
    assert proc.returncode == 2
```

- [ ] **Step 2: Run tests to verify the new ones fail**

Run: `.venv/bin/python -m pytest tests/test_run_status.py -v`
Expected: the 5 Task-2 tests pass; the new ones FAIL with `ImportError: cannot import name 'gate_verdict'`

- [ ] **Step 3: Append the implementation**

```python
# append to scripts/run_status.py
import argparse
import time

DEFAULT_SNAPSHOT = os.path.expanduser("~/.claude/usage-snapshot.json")
STALE_SECONDS = 900
WINDOWS = (("five_hour", "session (5-hour)"), ("seven_day", "weekly"))


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
    except (ValueError, KeyError, TypeError):
        return "PROCEED (gate degraded: unreadable usage snapshot at %s)" % snapshot_path
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


def main():
    ap = argparse.ArgumentParser(
        description="Run state + usage gate for a translation run (see module docstring).")
    ap.add_argument("work_dir", help="the run's work directory (contains chunks.json)")
    ap.add_argument("--gate", action="store_true", help="also print a PROCEED/PAUSE verdict")
    ap.add_argument("--threshold", type=float, default=90.0)
    ap.add_argument("--snapshot", default=DEFAULT_SNAPSHOT)
    ap.add_argument("--now", type=float, default=None, help="epoch override for tests")
    args = ap.parse_args()

    if not os.path.isdir(args.work_dir):
        ap.exit(2, "run_status: work dir not found: %s\n" % args.work_dir)

    state = chunk_state(args.work_dir)
    if state.get("not_chunked"):
        print("not chunked yet — no chunks.json in %s; restart from step 1 (ingest)"
              % args.work_dir)
    else:
        print("chunks: %d total, %d done, %d missing"
              % (state["total"], len(state["done"]), len(state["missing"])))
        if state["missing"]:
            print("missing: %s" % ", ".join("chunk_%04d" % i for i in state["missing"]))
        print("state: %s" % json.dumps(state))

    if args.gate:
        print("gate: %s" % gate_verdict(args.snapshot, args.threshold, args.now))


if __name__ == "__main__":
    main()
```

Note: move the `import argparse` / `import time` lines up to the module's import block (with
`import json` / `import os`) rather than mid-file — the comment above marks what's new, not
where imports live.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_run_status.py -v`
Expected: 18 passed

- [ ] **Step 5: Validate read-only against the real runs**

Run: `.venv/bin/python -m scripts.run_status runs/alminhaj/work --gate`
Expected: `chunks: N total, N done, 0 missing` (complete book) + a `gate:` line (PROCEED or
degraded, depending on whether the statusline is installed yet — degraded is correct before Task 4).

Run: `.venv/bin/python -m scripts.run_status runs/bawsala/work`
Expected: partial state — some chunks done, the rest listed as missing. Sanity-check the missing
list against `ls runs/bawsala/work/translated/`.

- [ ] **Step 6: Run the full suite**

Run: `.venv/bin/python -m pytest -m "not integration"`
Expected: all pass

- [ ] **Step 7: Commit**

```bash
git add scripts/run_status.py tests/test_run_status.py
git commit -m "feat(resilience): usage gate verdict + run_status CLI"
```

---

### Task 4: install the statusline (user-global, outside the repo)

**Files:**
- Modify: `~/.claude/settings.json` (add `statusLine` key — MERGE, do not overwrite existing keys)
- Create: `~/.claude/statusline_usage.py` (copy of the repo file)

**Interfaces:**
- Consumes: `scripts/statusline_usage.py` from Task 1.
- Produces: a live `~/.claude/usage-snapshot.json` that Task 3's default `--snapshot` path reads. No repo changes — nothing to commit in this task.

- [ ] **Step 1: Copy the script**

```bash
cp scripts/statusline_usage.py ~/.claude/statusline_usage.py
```

- [ ] **Step 2: Add the statusLine entry (merge into existing settings)**

```bash
python3 - <<'EOF'
import json, os
p = os.path.expanduser("~/.claude/settings.json")
s = json.load(open(p))
s["statusLine"] = {"type": "command",
                   "command": "python3 ~/.claude/statusline_usage.py"}
json.dump(s, open(p, "w"), indent=2)
print(json.dumps(s["statusLine"]))
EOF
```

Expected output: `{"type": "command", "command": "python3 ~/.claude/statusline_usage.py"}` — and
`~/.claude/settings.json` must still contain its previous keys (`permissions`, `model`,
`enabledPlugins`, …). Verify: `python3 -c "import json,os; print(sorted(json.load(open(os.path.expanduser('~/.claude/settings.json'))).keys()))"`

- [ ] **Step 3: Smoke-test the installed copy**

```bash
echo '{"model":{"display_name":"Fable"},"rate_limits":{"five_hour":{"used_percentage":10,"resets_at":1751912345}}}' \
  | python3 ~/.claude/statusline_usage.py
cat ~/.claude/usage-snapshot.json
```

Expected: first command prints `Fable · session 10% · resets <local HH:MM>`; the cat shows
`written_at` + a `five_hour` block. NOTE: this smoke test writes the real snapshot file with fake
data — fine, the next real statusline render (any Claude Code activity after install) overwrites
it, and it goes stale after 15 minutes anyway.

- [ ] **Step 4: Tell the user**

The live statusline appears in NEW Claude Code sessions (and the snapshot then refreshes on every
API response). Report to the user that the statusline is installed and what it shows.

---

### Task 5: SKILL.md — usage gate, RESUME.md checklist, resume procedure

**Files:**
- Modify: `SKILL.md` (three edits: setup bullet; step 5 bullet; new section before "Non-negotiables")

**Interfaces:**
- Consumes: the exact CLI from Task 3 (`python -m scripts.run_status <book>/work --gate`) and the install from Task 4.
- Produces: the orchestrator behavior — gate before every wave; RESUME.md on any early stop; resume procedure.

- [ ] **Step 1: Add the one-time setup bullet**

In the `## One-time setup` list, after the fonts bullet, add:

```markdown
- **Usage gate (recommended):** `cp scripts/statusline_usage.py ~/.claude/` and add to
  `~/.claude/settings.json`: `"statusLine": {"type": "command", "command": "python3
  ~/.claude/statusline_usage.py"}`. This tees live usage percentages to
  `~/.claude/usage-snapshot.json` for the translate-step gate (and shows them in the terminal).
  Without it the gate degrades gracefully: runs proceed with a stated warning.
```

- [ ] **Step 2: Add the usage-gate bullet to step 5**

In `## Per book` step 5 (**Translate (parallel subagents)**), insert a new first bullet ABOVE
**Pilot gate**:

```markdown
   - **Usage gate**: before the pilot and before EVERY subsequent wave, run
     `python -m scripts.run_status <book>/work --gate` (`--threshold N` overrides the default
     90). On `PAUSE`: do not dispatch — write RESUME.md (see "Pausing and resuming a run"), tell
     the user the reset time, and stop cleanly. A degraded verdict states its reason and
     proceeds. The percentages printed at each wave show the burn per wave — mention them to the
     user when tuning `--threshold`.
```

- [ ] **Step 3: Add the pause/resume section**

Insert between the end of `## Per book` (after step 9) and `## Non-negotiables`:

```markdown
## Pausing and resuming a run

A run can stop early — usage-gate PAUSE, a crash, a closed session — and loses at most the
in-flight wave: completed chunks are already in `<book>/work/translated/`.

**On any early stop, write `<book>/RESUME.md`** from `python -m scripts.run_status <book>/work`
plus what only you know:

- Book title (Arabic + English) and the work dir.
- Chunk state: N done / M missing, listing the missing chunk numbers.
- The exact commands with their run-specific flags (`--target` used at chunk time,
  `--no-hadith-numbers` at assemble, …) and the glossary path.
- Which usage window tripped and its reset time (from the gate verdict), when applicable.
- The one-line instruction for the user: "Resume the <book> run in <work dir>".

**To resume:** run `python -m scripts.run_status <book>/work`; confirm `structure.json` and
`glossary.json` exist; dispatch subagents for the MISSING chunks only (same template, same wave
discipline — the usage gate applies to resumed waves too); then continue from step 6 unchanged
(assemble reads whatever is in `translated/`). No `chunks.json` = nothing to resume; restart
from step 1 (the ingest steps are cheap).
```

- [ ] **Step 4: Re-read the modified SKILL.md end-to-end**

Verify: the three insertions read coherently in place; step numbering is unchanged; no duplicate
gate instructions; the section referenced by the step-5 bullet ("Pausing and resuming a run")
exists with exactly that title.

- [ ] **Step 5: Commit**

```bash
git add SKILL.md
git commit -m "docs(skill): usage gate before every wave + pause/resume procedure"
```
