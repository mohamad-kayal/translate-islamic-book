# Run resilience: usage-aware pausing + resumable runs — design

Date: 2026-07-07 · Status: approved in brainstorm (manual resume; statusline-snapshot gate; fail-open)

## Problem

A full book run dispatches 10–13 chunk-translation subagent waves and can hit the subscription
usage limit (5-hour session window, or the 7-day window) mid-book. Today that death is messy: the
orchestrator turn and in-flight subagents die on a 429, no handoff document exists, and the user
must reconstruct run state by hand. Goal: a run never loses more than the in-flight wave, stops
*cleanly before* the wall when it can see it coming, and resumes with one sentence after reset.

## Decisions (locked)

1. **Manual resume.** On pause the run stops cleanly and writes `RESUME.md`; the user re-opens
   Claude Code after reset and says "resume the <book> run". No auto-scheduling, no cron.
2. **Gate mechanism = statusline snapshot.** A statusline script tees Claude Code's rate-limit
   JSON to a snapshot file; the orchestrator reads it before each dispatch wave.
3. **Fail-open.** Gate infrastructure failure (missing/stale/malformed snapshot) warns and
   proceeds — worst case is the pre-feature status quo, and resumability is the net underneath.
4. **Threshold default 90**, tunable per run via `--threshold` (gate fires between waves; an
   in-flight wave of ≤8 Opus subagents still burns usage the gate cannot see, so 97 is too late).
5. **Both windows gate**: `five_hour` and `seven_day` — whichever first reaches the threshold
   trips the pause; the verdict names which one and its reset time.

## Verified facts (researched 2026-07-07, claude-code-guide + local inspection)

- The model **cannot** query its own usage: `/usage` renders to the human only; hook input JSON
  carries no rate-limit fields; no CLI/API/cache exposes subscription windows
  (`~/.claude/stats-cache.json` is lifetime/daily aggregates only).
- Statusline scripts receive session JSON on stdin on every render, including
  `rate_limits.five_hour.used_percentage` (0–100), `rate_limits.five_hour.resets_at` (epoch), and
  the `seven_day` equivalents. Present for Pro/Max subscribers after the first API response —
  i.e. continuously fresh during an active run.
- The terminal's "approaching limit" warning is UI-only; it is never injected into model context.
- When the wall hits mid-turn: HTTP 429, the turn and in-flight subagents die, the session
  survives, and completed `translated/chunk_NNNN.md` files survive on disk.
- The user's `~/.claude/settings.json` currently has **no** `statusLine` entry (clean slate).

## Components

### `scripts/statusline_usage.py` — snapshot writer

Invoked by Claude Code as the statusline command; reads the session JSON from stdin. Atomically
writes (temp file + `os.replace` in the same directory) `~/.claude/usage-snapshot.json`:

```json
{
  "written_at": 1751900000,
  "five_hour": {"used_percentage": 42.0, "resets_at": 1751912345},
  "seven_day": {"used_percentage": 13.5, "resets_at": 1752300000}
}
```

Also prints a one-line statusline (side benefit): `model · session NN% · week NN% · resets HH:MM`.
Missing `rate_limits` in the input (API-key users, first render) → still print the line, skip the
snapshot write. Never crash: any error → print a minimal line, exit 0 (a broken statusline nags
every render).

**Install (one-time, documented in SKILL.md setup):** copy to `~/.claude/statusline_usage.py` and
add the `statusLine` entry to `~/.claude/settings.json` pointing at the *copy* — the global config
must not break if this repo moves.

### `scripts/run_status.py` — state report + gate

`python -m scripts.run_status <book>/work [--gate] [--threshold 90] [--snapshot PATH] [--now EPOCH]`

- Always: diff `chunks.json` vs `translated/chunk_*.md` → JSON + human summary: total, done ids,
  missing ids. Absent `chunks.json` → say "not chunked yet — restart from step 1" (still exit 0).
- With `--gate`: read the snapshot and append a verdict line:
  - `PROCEED` — all windows under threshold (print current percentages), or
  - `PAUSE` — name the tripped window, its percentage, and `resets_at` as local time, or
  - `PROCEED (gate degraded: <reason>)` — snapshot missing, malformed, or stale (`written_at`
    older than 15 minutes vs `--now`/wall clock).
- `--snapshot` and `--now` exist so tests never touch the real `~/.claude` or the real clock.
- Exit code 0 in all cases (verdicts and state are for the orchestrator to read, not shell
  logic); nonzero only for an unreadable/nonexistent work dir path.

### `RESUME.md` — written by the orchestrator, not by code

SKILL.md gains a checklist; on any early stop the orchestrator writes `<book>/RESUME.md` from
`run_status` facts plus run context only it knows:

- Book title (Arabic + English) and work dir.
- Chunk state: N done / M missing (list the missing ids).
- The exact commands with their run-specific flags (`--target` used at chunk time,
  `--no-hadith-numbers` at assemble, etc.) and the glossary path.
- Which window tripped and the reset time.
- The one-line resume instruction for the user to paste after reset.

### SKILL.md changes

- **Setup**: one-time statusline install step (copy + settings entry); note the gate degrades
  gracefully without it.
- **Step 5 (translate)**: run the gate before the pilot chunk and before *every* subsequent wave;
  on PAUSE → write RESUME.md, report the reset time to the user, stop cleanly. The gate's printed
  percentages each wave show burn-per-wave, informing threshold tuning.
- **New section "Resuming a run"**: run `run_status`; confirm `structure.json` and
  `glossary.json` exist; dispatch subagents for missing chunks only (same template, same wave
  discipline, gate still applies); continue from step 6 unchanged — assemble already reads
  whatever is in `translated/`. A resume needs no special assembly path.

## Flow

Statusline refreshes the snapshot after every API response (constant during a run). Orchestrator
loop: `run_status --gate` → PROCEED → dispatch ≤8 subagents → chunks land → gate → … → PAUSE →
RESUME.md → report → stop. After reset: fresh session, "resume the <book> run", missing chunks
only, pipeline continues at step 6.

## Error handling

- Gate never blocks on its own failure (decision 3); every degraded PROCEED states the reason.
- Wall hits mid-wave anyway: failed wave's chunks are simply "missing"; the normal resume
  procedure recovers them. No special crash path exists or is needed.
- Limit hits before chunking: nothing to resume; restart the cheap ingest steps (steps 1–4).
- Snapshot staleness guards against gating a fresh run on last week's numbers.

## Testing (pytest, matching repo style)

- `run_status` state diff: full / partial / empty `translated/`, absent `chunks.json`.
- Gate verdicts: under/over threshold on each window, both-over (first named wins), missing /
  malformed / stale snapshot via `--snapshot` + `--now` injection.
- `statusline_usage.py`: fed a sample stdin JSON → snapshot written atomically with correct
  fields; input without `rate_limits` → line printed, no snapshot write; garbage stdin → exit 0.
- Real-world validation: dispatch the live bawsala run's remaining chunks through the new gate +
  resume path.

## Out of scope (deliberate, YAGNI)

- Auto-resume scheduling (cron / scheduled agents / headless relaunch).
- Persistent burn-per-wave logging (gate prints percentages; tune by eye).
- Predictive gating (estimating a wave's cost before dispatch).
- Any pause/resume handling for the cheap non-wave phases (ingest, ToC, assemble, verify).
