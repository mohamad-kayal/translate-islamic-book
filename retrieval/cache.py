"""Pickle cache for parsed retrieval datasets.

Building the hadith index parses ~20 JSON files and normalizes ~40k matns on EVERY
`python -m retrieval.hadith_lookup` call (~11 s measured) — and translator subagents
make one call per hadith. Caching the parsed payload cuts that to the pickle-load cost.

The cache is valid only while every source file's (path, mtime_ns, size) fingerprint
and the schema number are unchanged. Every failure mode — missing/corrupt/stale pickle,
unreadable source, unwritable cache dir — falls back to a fresh build (fail open):
a broken cache can cost time, never correctness. RETRIEVAL_NO_CACHE=1 disables caching.
"""
import os
import pickle

SCHEMA = 1   # bump when a cached payload's shape changes

_MISSING = (None, None)


def _fingerprint(paths):
    """[(path, mtime_ns, size)] per source; a missing file records as (path, None, None)
    so an optional source (e.g. english-fixes.json) may be absent — and its later
    appearance invalidates the cache."""
    fp = []
    for p in paths:
        p = os.path.abspath(p)
        try:
            st = os.stat(p)
            fp.append((p, st.st_mtime_ns, st.st_size))
        except OSError:
            fp.append((p,) + _MISSING)
    return fp


def load_cached(name, source_paths, build, cache_dir, schema=SCHEMA):
    """Return build()'s payload, cached at <cache_dir>/<name>.pkl."""
    if os.environ.get("RETRIEVAL_NO_CACHE"):
        return build()
    path = os.path.join(cache_dir, "%s.pkl" % name)
    fp = _fingerprint(source_paths)
    try:
        with open(path, "rb") as f:
            cached = pickle.load(f)
        if cached["schema"] == schema and cached["fingerprint"] == fp:
            return cached["payload"]
    except Exception:
        pass
    payload = build()
    try:
        os.makedirs(cache_dir, exist_ok=True)
        tmp = "%s.tmp.%d" % (path, os.getpid())
        with open(tmp, "wb") as f:
            pickle.dump({"schema": schema, "fingerprint": fp, "payload": payload},
                        f, protocol=pickle.HIGHEST_PROTOCOL)
        os.replace(tmp, path)   # atomic: parallel subagents never see a half-written cache
    except Exception:
        pass
    return payload
