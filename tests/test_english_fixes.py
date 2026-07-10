"""data/english-fixes.json: sign-off-gated corrections to dataset English.

The bundled hadith English carries OCR damage (U+FFFD, "brot'ier", the Thawban
"last"->"cast" typo) that otherwise must be re-flagged in every book's review.md.
A fix entry is applied at index load, so lookup and verify both see the corrected
text; entries are added only after the user signs off (governance in SKILL.md).
"""
import json

from retrieval.hadith_index import HadithIndex

MATN = "يوشك الامم ان تداعى عليكم"


def _write_dataset(tmp_path, english):
    hd = tmp_path / "hadith"
    hd.mkdir(exist_ok=True)
    (hd / "ara-abudawud.json").write_text(
        json.dumps({"hadiths": [{"hadithnumber": 4297, "text": MATN, "reference": {}}]},
                   ensure_ascii=False), encoding="utf-8")
    (hd / "eng-abudawud.json").write_text(
        json.dumps({"hadiths": [{"hadithnumber": 4297, "text": english}]},
                   ensure_ascii=False), encoding="utf-8")
    return str(hd)


def _write_fixes(tmp_path, fixes):
    (tmp_path / "english-fixes.json").write_text(
        json.dumps({"fixes": fixes}, ensure_ascii=False), encoding="utf-8")


def test_fix_applied_at_load(tmp_path):
    d = _write_dataset(tmp_path, "Allah will last enervation into your hearts")
    _write_fixes(tmp_path, [{"collection": "abudawud", "number": 4297,
                             "old": "will last enervation", "new": "will cast enervation",
                             "note": "OCR typo", "approved": "2026-07-10"}])
    e = HadithIndex.load(data_dir=d).get("abudawud", 4297)
    assert "will cast enervation" in e["english"]
    assert "will last" not in e["english"]


def test_absent_fixes_file_is_fine(tmp_path):
    d = _write_dataset(tmp_path, "unchanged text")
    e = HadithIndex.load(data_dir=d).get("abudawud", 4297)
    assert e["english"] == "unchanged text"


def test_stale_fix_warns_but_does_not_break(tmp_path, capsys):
    d = _write_dataset(tmp_path, "the dataset was already corrected upstream")
    _write_fixes(tmp_path, [{"collection": "abudawud", "number": 4297,
                             "old": "no longer present", "new": "x",
                             "note": "", "approved": "2026-07-10"}])
    e = HadithIndex.load(data_dir=d).get("abudawud", 4297)
    assert e["english"] == "the dataset was already corrected upstream"
    assert "not found" in capsys.readouterr().err


def test_fix_for_other_number_not_applied(tmp_path):
    d = _write_dataset(tmp_path, "will last enervation")
    _write_fixes(tmp_path, [{"collection": "abudawud", "number": 1,
                             "old": "will last enervation", "new": "will cast enervation",
                             "note": "", "approved": "2026-07-10"}])
    e = HadithIndex.load(data_dir=d).get("abudawud", 4297)
    assert "will last enervation" in e["english"]


def test_fixes_file_appearing_later_invalidates_cache(tmp_path):
    d = _write_dataset(tmp_path, "Allah will last enervation into your hearts")
    assert "will last" in HadithIndex.load(data_dir=d).get("abudawud", 4297)["english"]
    _write_fixes(tmp_path, [{"collection": "abudawud", "number": 4297,
                             "old": "will last", "new": "will cast",
                             "note": "", "approved": "2026-07-10"}])
    assert "will cast" in HadithIndex.load(data_dir=d).get("abudawud", 4297)["english"]


def test_shipped_fixes_file_is_valid_and_empty_pending_signoff():
    import os
    path = os.path.join(os.path.dirname(__file__), "..", "data", "english-fixes.json")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    assert isinstance(data["fixes"], list)
    for fix in data["fixes"]:   # every shipped entry must be complete + signed off
        assert {"collection", "number", "old", "new", "note", "approved"} <= set(fix)
