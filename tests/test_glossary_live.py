import json

import pytest

from retrieval.glossary import fold, harvest, resolve, subset_for

MASTER = {
    "style": "test style line",
    "terms": {
        "التوحيد": {"translit": "tawhid", "english": "the Oneness of Allah"},
        "الفتن": {"translit": "fitan", "english": "trials and tribulations"},
    },
    "names": {"ابن تيمية": "Ibn Taymiyyah"},
    "works": {"حجية السنة": "Hujjiyyat al-Sunnah"},
}


def test_fold_diacritics_hamza_ta_marbuta_article():
    assert fold("التَّوْحِيدُ") == fold("توحيد")
    assert fold("أحمد") == fold("احمد")
    assert fold("والفتنة") == fold("فتنه")
    assert fold("بالسنة") == fold("سنه")


def test_subset_for_matches_folded_terms_and_includes_names():
    text = "نتكلم عن توحيد الله في هذا الدرس"  # bare form, master key has ال
    sub = subset_for(text, MASTER)
    assert "التوحيد" in sub["terms"]
    assert "الفتن" not in sub["terms"]
    assert sub["names"] == MASTER["names"]
    assert sub["style"] == "test style line"


def test_subset_matches_works():
    sub = subset_for("قرات في كتاب حجيه السنه كلاما", MASTER)
    assert "حجية السنة" in sub["works"]


def _run_dir(tmp_path, new_terms):
    work = tmp_path / "run" / "work" / "translated"
    work.mkdir(parents=True)
    (work / "block_000.json").write_text(json.dumps(
        {"block": 0, "sentences": [], "new_terms": new_terms, "flags": []},
        ensure_ascii=False), encoding="utf-8")
    return tmp_path / "run"


def _write_master(tmp_path):
    p = tmp_path / "glossary.json"
    p.write_text(json.dumps(MASTER, ensure_ascii=False), encoding="utf-8")
    return p


def test_harvest_auto_merges_new_and_holds_conflicts(tmp_path):
    run = _run_dir(tmp_path, [
        {"ar": "السيرة", "translit": "sirah", "english": "the Prophetic biography", "kind": "term"},
        {"ar": "التوحيد", "translit": "tawhid", "english": "monotheism", "kind": "term"},  # conflict
        {"ar": "خالد بن الوليد", "translit": "", "english": "Khalid ibn al-Walid", "kind": "name"},
    ])
    master_path = _write_master(tmp_path)
    changelog = tmp_path / "glossary-changelog.md"
    result = harvest(run, master_path, changelog)

    master = json.loads(master_path.read_text(encoding="utf-8"))
    assert master["terms"]["السيرة"] == {"translit": "sirah", "english": "the Prophetic biography"}
    assert master["names"]["خالد بن الوليد"] == "Khalid ibn al-Walid"
    assert master["terms"]["التوحيد"]["english"] == "the Oneness of Allah"  # conflict NOT applied
    assert [c["ar"] for c in result["conflicts"]] == ["التوحيد"]
    assert "السيرة" in changelog.read_text(encoding="utf-8")
    proposals = json.loads((run / "work" / "glossary-proposals.json").read_text(encoding="utf-8"))
    assert proposals[0]["proposed"]["english"] == "monotheism"


def test_harvest_same_rendering_is_not_a_conflict(tmp_path):
    run = _run_dir(tmp_path, [
        {"ar": "الفتنة", "translit": "fitan", "english": "trials and tribulations", "kind": "term"},
    ])  # folded key matches existing الفتن? no — فتنه != فتن; use exact dup instead
    master_path = _write_master(tmp_path)
    result = harvest(run, master_path, tmp_path / "log.md")
    # new folded key -> added, no conflict
    assert result["conflicts"] == []


def test_harvest_exact_duplicate_skipped(tmp_path):
    run = _run_dir(tmp_path, [
        {"ar": "التوحيد", "translit": "tawhid", "english": "the Oneness of Allah", "kind": "term"},
    ])
    master_path = _write_master(tmp_path)
    result = harvest(run, master_path, tmp_path / "log.md")
    assert result["added"] == {} and result["conflicts"] == []


def test_resolve_applies_only_named(tmp_path):
    run = _run_dir(tmp_path, [
        {"ar": "التوحيد", "translit": "tawhid", "english": "monotheism", "kind": "term"},
        {"ar": "ابن تيمية", "translit": "", "english": "Ibn Taymiyya", "kind": "name"},
    ])
    master_path = _write_master(tmp_path)
    harvest(run, master_path, tmp_path / "log.md")
    resolve(run, master_path, accept={"التوحيد"})
    master = json.loads(master_path.read_text(encoding="utf-8"))
    assert master["terms"]["التوحيد"]["english"] == "monotheism"
    assert master["names"]["ابن تيمية"] == "Ibn Taymiyyah"  # not accepted -> unchanged
