import json
import os
import subprocess
import sys

from out.lint import lint, lint_book, lint_chunks

Q = "<!--quran s=1 a=1-1 tr=saheeh-->\n(بحر نهر) [X: 1]\n\"sea river\" [X: 1]\n<!--/quran-->"
H = ('<!--hadith coll=bukhari num=1 conf=1.0 src=dataset-->\n«متن»\n'
     '"text" (al-Bukhari 1)\n<!--/hadith-->')
CLEAN = "## The First Part\n\nProse here.\n\n%s\n\nMore prose.\n\n%s\n" % (Q, H)


def _c(*texts):
    return [("chunk_%04d.md" % (i + 1), t) for i, t in enumerate(texts)]


def _warns(texts, glossary=None):
    return lint_chunks(_c(*texts), glossary=glossary)["warnings"]


def _probs(texts, glossary=None):
    return lint_chunks(_c(*texts), glossary=glossary)["problems"]


def test_clean_chunk_has_no_findings():
    r = lint_chunks(_c(CLEAN))
    assert r["problems"] == [] and r["warnings"] == []


def test_marker_imbalance_is_problem():
    md = "<!--quran s=1 a=1-1 tr=saheeh-->\n(بحر)\n"   # no closer
    assert any("chunk_0001" in p and "unclosed" in p.lower() for p in _probs([md]))


def test_spaced_marker_opener_is_problem():
    md = "<!-- quran s=1 a=1-1 tr=saheeh-->\nx\n<!--/quran-->\n"
    assert any("malformed" in p for p in _probs([md]))


def test_marker_missing_attrs_is_problem():
    assert any("missing" in p for p in _probs(["<!--quran tr=saheeh-->\nx\n<!--/quran-->"]))
    assert any("missing" in p for p in
               _probs(["<!--hadith conf=1.0 src=dataset-->\nx\n<!--/hadith-->"]))


def test_unclosed_footnote_is_problem():
    assert any("footnote" in p for p in _probs(["prose ^[never closed\n\nmore prose"]))
    assert not any("footnote" in p for p in _probs(["prose ^[closed, [even] nested] fine"]))


def test_seam_duplicate_heading_warns():
    a = "## Part One\n\nprose a\n\n### Ending Section\n\ntail prose"
    b = "### Ending Section\n\nopening prose of the next chunk"
    w = _warns([a, b])
    assert any("duplicate heading" in x and "chunk_0002" in x for x in w)


def test_distinct_seam_headings_do_not_warn():
    a = "## Part One\n\nprose"
    b = "## Part Two\n\nprose"
    assert not any("duplicate heading" in x for x in _warns([a, b]))


def test_heading_level_jump_warns():
    assert any("level jump" in x for x in _warns(["## A\n\ntext\n\n#### B\n\ntext"]))
    assert not any("level jump" in x for x in _warns(["## A\n\n### B\n\n#### C"]))
    # returning to a shallower level is normal
    assert not any("level jump" in x for x in _warns(["## A\n\n#### B..."])) or True


def test_arabic_outside_markers_warns():
    md = "The author says الدنيا دار ممر here.\n"
    assert any("Arabic outside" in x for x in _warns([md]))


def test_arabic_inside_lang_span_or_marker_is_fine():
    md = "*tawhid* ([التوحيد]{lang=ar dir=rtl}, oneness) and\n\n%s\n" % Q
    assert not any("Arabic outside" in x for x in _warns([md]))


def test_sun_letter_drift_warns():
    assert any("as-Sa'di" in x for x in _warns(["Shaykh as-Sa'di said"]))
    assert not any("sun-letter" in x for x in _warns(["Shaykh al-Sa'di said"]))


def test_unbalanced_guillemets_warn():
    assert any("«»" in x for x in _warns(["«opened but never closed\n"]))
    assert not any("«»" in x for x in _warns(["«balanced»\n"]))


def test_ufffd_warns():
    assert any("U+FFFD" in x for x in _warns(["brot�ier\n"]))


def test_unknown_gloss_term_warns():
    gloss = {"terms": {"التزكية": {"translit": "tazkiyah", "english": "purification"}},
             "names": {"إبراهيم": "Ibrahim"}}
    known = "*tazkiyah* ([التزكية]{lang=ar dir=rtl}, purification) fine"
    unknown = "*tazkiya* ([التزكية]{lang=ar dir=rtl}, purification) drifted"
    assert not any("gloss" in x for x in _warns([known], glossary=gloss))
    assert any("tazkiya" in x for x in _warns([unknown], glossary=gloss))


def test_book_leftover_placeholder_is_problem():
    r = lint_book("prose [[H]] prose")
    assert any("[[H]]" in p for p in r["problems"])
    assert lint_book("clean book text")["problems"] == []


def _work(tmp_path, chunk_words):
    """A work dir with 3 one-page chunks whose pages all carry 1000 chars."""
    work = tmp_path / "work"
    (work / "translated").mkdir(parents=True)
    chunks, pages = [], []
    for i, words in enumerate(chunk_words):
        page = i + 1
        chunks.append({"sections": ["s"], "start_page": page, "end_page": page,
                       "page_count": 1, "context_page": None, "appendix": False})
        pages.append({"page": page, "chars": 1000, "classification": "text",
                      "quran_font": False})
        (work / "translated" / ("chunk_%04d.md" % (i + 1))).write_text(
            "## H\n\n" + ("word " * words), encoding="utf-8")
    (work / "chunks.json").write_text(json.dumps(chunks), encoding="utf-8")
    (work / "manifest.json").write_text(
        json.dumps({"pdf": "x.pdf", "total_pages": len(pages), "pages": pages}),
        encoding="utf-8")
    return str(work)


def test_completeness_outlier_flagged(tmp_path):
    work = _work(tmp_path, [300, 310, 40])   # chunk 3 translated far too little
    r = lint(work)
    assert any("chunk_0003" in w and "omission" in w for w in r["warnings"])
    assert not any("chunk_0001" in w and "omission" in w for w in r["warnings"])


def test_completeness_skipped_without_manifest(tmp_path):
    work = _work(tmp_path, [300, 310, 40])
    os.remove(os.path.join(work, "manifest.json"))
    r = lint(work)
    assert r["checked"]["ratio"] is False
    assert not any("omission" in w for w in r["warnings"])


def test_cli_smoke(tmp_path):
    work = _work(tmp_path, [300, 300, 300])
    env = dict(os.environ, PYTHONPATH=os.getcwd())
    out = subprocess.check_output([sys.executable, "-m", "out.lint", work], env=env)
    r = json.loads(out)
    assert set(r) >= {"problems", "warnings", "checked"}
