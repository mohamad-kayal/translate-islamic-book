"""The one master glossary every format shares: folded matching, subsets, harvest, merge.

Matching folds orthography via ``retrieval.normalize.normalize_arabic`` plus definite-article
stripping, so ASR spellings (ة→ه, dropped hamza) and article variants all hit the same key.

``harvest`` is the "live document" mechanic for lectures and posts: brand-new folded keys
auto-merge into the master and are appended to the changelog; a folded key that already exists
with a DIFFERENT rendering becomes a conflict — written to ``<run>/work/glossary-proposals.json``
and never applied until ``resolve`` names it explicitly.

``diff``/``merge`` are the book equivalents, gated on the user's sign-off in review.md.

A term whose meaning depends on the discipline carries ``senses``: a list of
``{"context", "translit", "english"}`` alongside its default rendering. Translators pick by
context; a rendering that matches any sense is never reported as a conflict.
"""
import copy
import datetime
import json
import pathlib
import re

from retrieval.normalize import normalize_arabic

SECTIONS = ("terms", "names", "structure")

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


def mentioned(text, master):
    """subset_for, narrowed to the names the text also mentions. For clean written text;
    a lecture keeps every name because ASR mangles them."""
    folded = " %s " % fold(text)
    out = subset_for(text, master)
    out["names"] = {k: v for k, v in (master.get("names") or {}).items()
                    if " %s " % fold(k) in folded}
    return out


def prime(master, text=None):
    """A book's starting glossary: only the entries its text layer mentions, or the whole
    master when there is no usable text layer (image-only PDFs)."""
    if not text or len(normalize_arabic(text).split()) < 200:
        out = copy.deepcopy(master)
    else:
        out = mentioned(text, master)
        out["structure"] = dict(master.get("structure") or {})
    out["book"] = {}
    return out


def _load(path):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


load = _load


def _write_master(path, master):
    pathlib.Path(path).write_text(
        json.dumps(master, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")


def _collect_new_terms(run_dir):
    seen = {}
    work = pathlib.Path(run_dir) / "work"
    entries = []
    for block_file in sorted((work / "translated").glob("block_*.json")):
        entries += _load(block_file).get("new_terms") or []
    if (work / "new_terms.json").exists():     # posts have no blocks
        entries += _load(work / "new_terms.json")
    for entry in entries:
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
        elif _entry_differs(master[section][existing_key], value):
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


def _entry_differs(master_val, book_val):
    """Does this rendering disagree with the master? The book-only 'override' key is ignored
    and any of the term's recorded senses counts as agreement."""
    if not isinstance(book_val, dict) or not isinstance(master_val, dict):
        return master_val != book_val
    wanted = (book_val.get("translit"), book_val.get("english"))
    known = [master_val] + list(master_val.get("senses") or [])
    return wanted not in [(k.get("translit"), k.get("english")) for k in known]


def diff(master, book):
    """A book glossary's new entries and its conflicts against the master (folded keys)."""
    out = {"new_terms": {}, "new_names": {}, "new_structure": {}, "conflicts": []}
    for section in SECTIONS:
        m = master.get(section, {})
        folded = _folded_map(m)
        for arabic, book_val in (book.get(section, {}) or {}).items():
            has_override = isinstance(book_val, dict) and "override" in book_val
            key = arabic if arabic in m else folded.get(fold(arabic))
            if key is None:
                if not has_override:
                    out["new_%s" % section][arabic] = book_val
            elif _entry_differs(m[key], book_val) and not has_override:
                out["conflicts"].append({
                    "section": section, "arabic": arabic, "key": key,
                    "master": m[key], "book": book_val,
                    "override": None,
                })
    return out


def _clean(val):
    if isinstance(val, dict):
        return {k: v for k, v in val.items() if k != "override"}
    return val


_NEW_KEY_FOR_SECTION = {"terms": "new_terms", "names": "new_names", "structure": "new_structure"}


def merge(master, book, only=None):
    """Write approved entries from `book` into a copy of `master`.

    Reuses `diff` to classify entries so `merge`'s notion of "safe to write" matches
    what the sign-off proposals actually showed the user:
      - new_* entries (no override) are applied; `only` further restricts them to the
        named keys.
      - `override` entries are book-local deviations and are NEVER applied — `diff`
        already excludes them from new_*/conflicts, so they're untouched by construction.
      - conflicts (existing key, differing value, no override) are applied ONLY if their
        Arabic key is explicitly named in `only` — merging a conflict is an accept, and
        the user must name what they're accepting.
    """
    result = copy.deepcopy(master)
    d = diff(master, book)
    for section in SECTIONS:
        dest = result.setdefault(section, {})
        for arabic, book_val in d[_NEW_KEY_FOR_SECTION[section]].items():
            if only is not None and arabic not in only:
                continue
            dest[arabic] = _clean(book_val)
    if only:
        for c in d["conflicts"]:
            if c["arabic"] in only:
                dest = result.setdefault(c["section"], {})
                dest[c["key"]] = _clean(c["book"])
    return result
