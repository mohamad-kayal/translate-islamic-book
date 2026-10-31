"""Download PINNED Quran + hadith datasets into data/, guarded by a SHA-256 manifest.

The upstream repos (fawazahmed0/quran-api, hadith-api) version by a single MOVING
branch named "1" — no tags — so a bare @1 URL tracks their development tip and a
re-download could silently change sacred text under already-verified books. URLs
therefore pin exact COMMIT SHAs (immutable on the jsDelivr CDN), and
data/MANIFEST.json (git-tracked) records each file's SHA-256.

Musnad Ahmad and Sunan al-Darimi come from Open Hadith Data (Open Database License),
Arabic only. Its CSV is the pinned source; setup converts it to the hadith-api edition
shape so the index needs no special case.

Trust flow: when a manifest exists, setup VERIFIES downloads against it and exits
nonzero on any mismatch — it never silently rewrites the baseline. A fresh setup
(no manifest) writes one; bump the pins deliberately with --update-manifest.
    python scripts/setup_data.py             # download (skip existing) + verify
    python scripts/setup_data.py --check     # verify only, no downloads
    python scripts/setup_data.py --update-manifest   # re-baseline after a pin bump
"""
import argparse
import csv
import hashlib
import io
import json
import os
import subprocess
import sys
import time

QURAN_EDITIONS = ["ara-quranuthmanihaf", "eng-ummmuhammad", "eng-mustafakhattaba"]
HADITH_COLLECTIONS = ["bukhari", "muslim", "abudawud", "tirmidhi", "nasai",
                      "ibnmajah", "malik", "nawawi", "qudsi", "dehlawi"]
ARABIC_ONLY = {
    "ahmad": "Musnad_Ahmad_Ibn-Hanbal/musnad_ahmad_ibn-hanbal_ahadith_mushakkala.utf8.csv",
    "darimi": "Sunan_Al-Darimi/sunan_al-darimi_ahadith_mushakkala_mufassala.utf8.csv",
}
# Branch "1" HEADs resolved 2026-07-10; Open-Hadith-Data master resolved 2026-10-31.
# Immutable: both hosts serve commit-pinned content forever, and MANIFEST.json
# double-checks the bytes. (jsDelivr refuses the 29 MB Ahmad CSV, hence raw GitHub.)
API_REFS = {
    "quran-api": "6be8e17f2a0c13b1f33b1c3057f73cb28d5e848e",
    "hadith-api": "df57907be35291c91ad6a6691180e22ca9920784",
    "open-hadith-data": "1515f6cba21efed20d8916bf55acef1dffa0d2d5",
}
_CDN = "https://cdn.jsdelivr.net/gh/fawazahmed0/{api}@{ref}/editions/{name}.json"
_OPEN_HADITH = "https://raw.githubusercontent.com/mhashim6/Open-Hadith-Data/{ref}/{path}"
_CHAPTERS = "https://api.quran.com/api/v4/chapters?language=en"

DATA_DIR = os.environ.get(
    "RETRIEVAL_DATA_DIR",
    os.path.join(os.path.dirname(__file__), "..", "data"),
)


def edition_url(api, name):
    return _CDN.format(api=api, ref=API_REFS[api], name=name)


def open_hadith_url(path):
    return _OPEN_HADITH.format(ref=API_REFS["open-hadith-data"], path=path)


def chapters_url():
    return _CHAPTERS


def dataset_files():
    """Relative paths of every pinned dataset file (manifest scope)."""
    rel = ["quran/%s.json" % n for n in QURAN_EDITIONS]
    rel += ["hadith/%s-%s.json" % (pfx, c)
            for c in HADITH_COLLECTIONS for pfx in ("ara", "eng")]
    for c in ARABIC_ONLY:
        rel += ["hadith/src-%s.csv" % c, "hadith/ara-%s.json" % c]
    return rel


def _http_fetch(url):
    """Fetch bytes over HTTPS via the system `curl`, which uses the OS trust store.
    (The macOS python.org framework build ships no CA bundle, so urllib fails cert
    verification; curl verifies properly — important so sacred text can't be MITM'd.)"""
    try:
        r = subprocess.run(["curl", "-fsSL", "--max-time", "120", url],
                           check=True, capture_output=True)
    except FileNotFoundError:
        raise RuntimeError("`curl` is required to download datasets but was not found on PATH.")
    except subprocess.CalledProcessError as e:
        raise RuntimeError("Failed to download %s: %s"
                           % (url, e.stderr.decode(errors="replace")[:200]))
    return r.stdout


def download(url, dest, fetch=_http_fetch, skip_existing=True):
    """Fetch url -> dest. Returns True if downloaded, False if skipped."""
    if skip_existing and os.path.exists(dest) and os.path.getsize(dest) > 0:
        return False
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    data = fetch(url)
    with open(dest, "wb") as f:
        f.write(data)
    return True


def edition_from_csv(raw):
    """Open Hadith Data rows (number, text) as a hadith-api edition; deterministic bytes."""
    csv.field_size_limit(1 << 30)
    rows = csv.reader(io.StringIO(raw.decode("utf-8-sig")))
    return {"hadiths": [{"hadithnumber": int(number),
                         "text": " ".join(text.replace("\u200f", " ").split()),
                         "reference": {}}
                        for number, text in rows]}


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def manifest_path(data_dir):
    return os.path.join(data_dir, "MANIFEST.json")


def build_manifest(data_dir):
    """Manifest dict from the dataset files present in data_dir."""
    files = {}
    for rel in dataset_files():
        path = os.path.join(data_dir, rel)
        if not os.path.exists(path):
            continue
        files[rel] = {"sha256": file_sha256(path), "bytes": os.path.getsize(path)}
    return {"pins": dict(API_REFS), "fetched_at": time.strftime("%Y-%m-%d"),
            "files": files}


def write_manifest(data_dir):
    m = build_manifest(data_dir)
    with open(manifest_path(data_dir), "w", encoding="utf-8") as f:
        json.dump(m, f, indent=2, sort_keys=True)
        f.write("\n")
    return m


def check_manifest(data_dir):
    """Problems (empty = every manifest file present with matching hash)."""
    mp = manifest_path(data_dir)
    if not os.path.exists(mp):
        return ["no manifest at %s — run setup once to create it" % mp]
    with open(mp, encoding="utf-8") as f:
        manifest = json.load(f)
    problems = []
    if manifest.get("pins") != API_REFS:
        problems.append("manifest pins differ from setup_data.API_REFS — "
                        "bump deliberately with --update-manifest")
    for rel, info in sorted(manifest.get("files", {}).items()):
        path = os.path.join(data_dir, rel)
        if not os.path.exists(path):
            problems.append("%s: missing" % rel)
        elif file_sha256(path) != info["sha256"]:
            problems.append("%s: SHA-256 mismatch (local file differs from the "
                            "verified baseline)" % rel)
    return problems


def build_surah_names(chapters_payload, dest):
    rows = [{"number": c["id"], "arabic": c["name_arabic"], "en": c["name_simple"]}
            for c in chapters_payload["chapters"]]
    rows.sort(key=lambda r: r["number"])
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Download pinned datasets (see module docstring).")
    ap.add_argument("--check", action="store_true",
                    help="verify local files against data/MANIFEST.json; no downloads")
    ap.add_argument("--update-manifest", action="store_true",
                    help="re-baseline MANIFEST.json from the local files (after a pin bump)")
    args = ap.parse_args(argv)
    data = os.path.abspath(DATA_DIR)

    if args.check:
        problems = check_manifest(data)
        for p in problems:
            print("CHECK FAIL %s" % p)
        print("manifest check: %s" % ("OK" if not problems else "%d problem(s)" % len(problems)))
        return 1 if problems else 0

    for name in QURAN_EDITIONS:
        d = download(edition_url("quran-api", name), os.path.join(data, "quran", name + ".json"))
        print(("downloaded " if d else "skipped    ") + name)
    for coll in HADITH_COLLECTIONS:
        for pfx in ("ara", "eng"):
            name = "%s-%s" % (pfx, coll)
            d = download(edition_url("hadith-api", name), os.path.join(data, "hadith", name + ".json"))
            print(("downloaded " if d else "skipped    ") + name)

    for coll, path in ARABIC_ONLY.items():
        src = os.path.join(data, "hadith", "src-%s.csv" % coll)
        d = download(open_hadith_url(path), src)
        print(("downloaded " if d else "skipped    ") + "src-" + coll)
        dest = os.path.join(data, "hadith", "ara-%s.json" % coll)
        if d or not os.path.exists(dest):
            with open(src, "rb") as f:
                edition = edition_from_csv(f.read())
            with open(dest, "w", encoding="utf-8") as f:
                json.dump(edition, f, ensure_ascii=False, sort_keys=True)

    # surah_names.json is a small git-tracked snapshot (its source API is unpinnable);
    # only build it when absent.
    names_dest = os.path.join(data, "surah_names.json")
    if not os.path.exists(names_dest):
        payload = json.loads(_http_fetch(chapters_url()).decode("utf-8"))
        build_surah_names(payload, names_dest)
        print("surah_names.json: %d surahs" % len(payload["chapters"]))

    if args.update_manifest or not os.path.exists(manifest_path(data)):
        m = write_manifest(data)
        print("manifest written: %d files" % len(m["files"]))
        return 0
    problems = check_manifest(data)
    for p in problems:
        print("CHECK FAIL %s" % p)
    if problems:
        print("downloads do NOT match the verified baseline — investigate before "
              "translating (or re-baseline deliberately with --update-manifest)")
        return 1
    print("manifest check: OK (%d files)" % len(build_manifest(data)["files"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
