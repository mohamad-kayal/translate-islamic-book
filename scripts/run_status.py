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
