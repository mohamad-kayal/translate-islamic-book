"""Download pinned public-domain Quran + hadith datasets and surah names into data/."""
import json
import os
import subprocess
import sys

QURAN_EDITIONS = ["ara-quranuthmanihaf", "eng-ummmuhammad", "eng-mustafakhattaba"]
HADITH_COLLECTIONS = ["bukhari", "muslim", "abudawud", "tirmidhi", "nasai",
                      "ibnmajah", "malik", "nawawi", "qudsi", "dehlawi"]
_CDN = "https://cdn.jsdelivr.net/gh/fawazahmed0/{api}@1/editions/{name}.json"
_CHAPTERS = "https://api.quran.com/api/v4/chapters?language=en"

DATA_DIR = os.environ.get(
    "RETRIEVAL_DATA_DIR",
    os.path.join(os.path.dirname(__file__), "..", "data"),
)


def edition_url(api, name):
    return _CDN.format(api=api, name=name)


def chapters_url():
    return _CHAPTERS


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


def build_surah_names(chapters_payload, dest):
    rows = [{"number": c["id"], "arabic": c["name_arabic"], "en": c["name_simple"]}
            for c in chapters_payload["chapters"]]
    rows.sort(key=lambda r: r["number"])
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)


def main(argv=None):
    data = os.path.abspath(DATA_DIR)
    for name in QURAN_EDITIONS:
        d = download(edition_url("quran-api", name), os.path.join(data, "quran", name + ".json"))
        print(("downloaded " if d else "skipped    ") + name)
    for coll in HADITH_COLLECTIONS:
        for pfx in ("ara", "eng"):
            name = "%s-%s" % (pfx, coll)
            d = download(edition_url("hadith-api", name), os.path.join(data, "hadith", name + ".json"))
            print(("downloaded " if d else "skipped    ") + name)
    payload = json.loads(_http_fetch(chapters_url()).decode("utf-8"))
    build_surah_names(payload, os.path.join(data, "surah_names.json"))
    print("surah_names.json: %d surahs" % len(payload["chapters"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
