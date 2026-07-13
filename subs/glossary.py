"""The live master glossary: folded matching, per-block subset injection, harvest.

Matching folds orthography via ``retrieval.normalize.normalize_arabic`` plus definite-article
stripping, so ASR spellings (ة→ه, dropped hamza) and article variants all hit the same key.

``harvest`` is the "live document" mechanic: brand-new folded keys auto-merge into the master
and are appended to the changelog; a folded key that already exists with a DIFFERENT rendering
becomes a conflict — written to ``<run>/work/glossary-proposals.json`` and never applied until
``resolve`` names it explicitly.
"""
import datetime
import json
import pathlib
import re

from retrieval.normalize import normalize_arabic

_ARTICLE = re.compile(r"^(?:وال|فال|بال|كال|ولل|لل|ال)")


def fold(text):
    tokens = normalize_arabic(text).split()
    return " ".join(_ARTICLE.sub("", t) or t for t in tokens)


def _folded_map(section):
    return {fold(k): k for k in section}


def subset_for(text, master):
    folded = " %s " % fold(text)
    out = {"style": master.get("style", ""), "terms": {}, "names": dict(master.get("names", {})),
           "works": {}}
    for section in ("terms", "works"):
        for key, val in (master.get(section) or {}).items():
            if " %s " % fold(key) in folded:
                out[section][key] = val
    return out


def _load(path):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def _write_master(path, master):
    pathlib.Path(path).write_text(
        json.dumps(master, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")


def _collect_new_terms(run_dir):
    seen = {}
    for block_file in sorted((pathlib.Path(run_dir) / "work" / "translated").glob("block_*.json")):
        for entry in _load(block_file).get("new_terms") or []:
            key = fold(entry.get("ar", ""))
            if key and key not in seen:
                seen[key] = entry
    return seen


def harvest(run_dir, master_path, changelog_path):
    """Auto-merge brand-new entries; hold conflicts. Returns {"added", "conflicts"}."""
    run_dir = pathlib.Path(run_dir)
    master = _load(master_path)
    added, conflicts = {}, []
    folded = {"terms": _folded_map(master.get("terms", {})),
              "names": _folded_map(master.get("names", {}))}
    for key, entry in _collect_new_terms(run_dir).items():
        section = "names" if entry.get("kind") == "name" else "terms"
        value = (entry.get("english", "") if section == "names"
                 else {"translit": entry.get("translit", ""), "english": entry.get("english", "")})
        existing_key = folded[section].get(key)
        if existing_key is None:
            master.setdefault(section, {})[entry["ar"]] = value
            folded[section][key] = entry["ar"]
            added[entry["ar"]] = {"section": section, "value": value}
        elif master[section][existing_key] != value:
            conflicts.append({"section": section, "ar": entry["ar"],
                              "existing_key": existing_key,
                              "master": master[section][existing_key],
                              "proposed": value})
    if added:
        _write_master(master_path, master)
        lines = ["", "## %s — %s" % (datetime.date.today().isoformat(), run_dir.name)]
        for ar, info in added.items():
            val = info["value"]
            rendered = val if isinstance(val, str) else "%s, %s" % (val["translit"], val["english"])
            lines.append("- %s: %s → %s" % (info["section"], ar, rendered))
        changelog = pathlib.Path(changelog_path)
        prev = changelog.read_text(encoding="utf-8") if changelog.exists() else "# Glossary changelog\n"
        changelog.write_text(prev + "\n".join(lines) + "\n", encoding="utf-8")
    (run_dir / "work" / "glossary-proposals.json").write_text(
        json.dumps(conflicts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"added": added, "conflicts": conflicts}


def resolve(run_dir, master_path, accept):
    """Apply the named conflict proposals (by their proposed Arabic key) to the master."""
    proposals = _load(pathlib.Path(run_dir) / "work" / "glossary-proposals.json")
    master = _load(master_path)
    applied = []
    for c in proposals:
        if c["ar"] in accept or c["existing_key"] in accept:
            master.setdefault(c["section"], {})[c["existing_key"]] = c["proposed"]
            applied.append(c["ar"])
    if applied:
        _write_master(master_path, master)
    return applied
