import json
import os
import subprocess
import sys

import pytest

pytestmark = pytest.mark.integration
# Al-Minhaj Arabic source lives beside the skill repo (Documents/Translations/Arabic/).
SRC = os.path.join(os.path.dirname(__file__), "..", "..", "Arabic", "Alminhaj.pdf")


def _need():
    if not os.path.exists(SRC):
        pytest.skip("Al-Minhaj source not found at %s" % SRC)


def _run(args):
    env = dict(os.environ, PYTHONPATH=os.getcwd())
    return subprocess.run([sys.executable, "-m", "scripts.ingest_book"] + args,
                          capture_output=True, text=True, env=env)


def test_analyze_real_book(tmp_path):
    _need()
    r = _run(["analyze", SRC, "--work", str(tmp_path)])
    assert r.returncode == 0, r.stderr
    manifest = json.load(open(tmp_path / "manifest.json", encoding="utf-8"))
    assert manifest["total_pages"] == 140
    assert len(manifest["pages"]) == 140
    assert "toc_candidate_pages: [5, 6, 7]" in r.stdout   # full ToC span incl. continuations
    assert any(p["classification"] == "ornamental" for p in manifest["pages"])
    assert any(p["quran_font"] for p in manifest["pages"])


def test_chunk_from_structure(tmp_path):
    _need()
    struct = [{"title": "Ch1", "start_page": 15, "level": 1},
              {"title": "Ch2", "start_page": 20, "level": 1},
              {"title": "Ch3", "start_page": 29, "level": 1}]
    (tmp_path / "structure.json").write_text(json.dumps(struct, ensure_ascii=False), encoding="utf-8")
    r = _run(["chunk", SRC, "--work", str(tmp_path), "--target", "8"])
    assert r.returncode == 0, r.stderr
    chunks = json.load(open(tmp_path / "chunks.json", encoding="utf-8"))
    assert chunks and all("sections" in c and c["page_count"] >= 1 for c in chunks)
    assert chunks[0]["start_page"] == 15          # first section boundary preserved
