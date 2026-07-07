# Master Glossary + Bilingual Terminology Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A committed master glossary that every book primes from and harvests back into (with user sign-off), plus inline `*translit* (ARABIC, english)` first-use rendering and a back-of-book Glossary appendix.

**Architecture:** New `data/glossary.json` (three sections: `terms`/`names`/`structure`) is the source of truth. `scripts/glossary.py` diffs a per-book glossary against it and merges approved entries back. `out/assemble.py` gains `--glossary` to append a `## Glossary` section (terms only). `out/convert.py` styles the appendix and inline Arabic. `SKILL.md` + the translator template wire prime → translate → harvest. Spec: `docs/superpowers/specs/2026-07-07-glossary-terminology-design.md`.

**Tech Stack:** Python 3 stdlib only, pytest, pandoc (bracketed-span + fenced-div markdown).

## Global Constraints

- Stdlib only — no new dependencies.
- Run tests from repo root: `.venv/bin/python -m pytest tests/<file> -v`; full suite `-m "not integration"`.
- Glossary schema (all four keys present; per-entry `override` optional):
  ```json
  {"style": "<house transliteration rule string>",
   "terms":     {"<arabic>": {"translit": "<latin>", "english": "<gloss>"}},
   "names":     {"<arabic>": "<English name>"},
   "structure": {"<arabic>": "<English heading word>"}}
  ```
  A per-book glossary MAY additionally carry a `book` block (title/author metadata) and, on any entry that deliberately departs from the master, `"override": "<reason>"`.
- `terms` is the ONLY section that reaches the reader (inline gloss + appendix). `names` and `structure` are consistency-only, never in the appendix.
- Transliteration house style (verbatim into `style` and used for every entry): `al-` with no sun-letter assimilation; `'` for ʿayn/hamza; no macrons.
- Inline first-use format (body text, translator template): `*translit* ([ARABIC]{lang=ar dir=rtl}, english)`; later uses = the short `translit` alone.
- Appendix entry format (assemble output): `*translit* · [ARABIC]{lang=ar dir=rtl} · english`, one per line, sorted by `translit` casefold.
- Nothing merges into the master without the user's sign-off (harvest writes proposals to review.md; `merge` runs only after sign-off).
- Commit directly to `main`. NEVER `git push`.
- Match existing test style: plain pytest functions, small helpers, `%`-formatting.

---

### Task 1: glossary schema + `data/glossary.json` seed + `scripts/glossary.py` (load + diff)

**Files:**
- Create: `data/glossary.json`
- Create: `scripts/glossary.py`
- Test: `tests/test_glossary.py`

**Interfaces:**
- Produces: `load(path) -> dict`; `diff(master: dict, book: dict) -> dict` returning
  `{"new_terms": {ar: val}, "new_names": {ar: val}, "new_structure": {ar: val}, "conflicts": [{"section","arabic","master","book","override"}]}`.
  A conflict = an Arabic key present in both, with a different value AND no `override` on the book entry. An entry with an `override` is NOT a conflict (it is an intentional book-local deviation) and is NOT "new". Task 2 adds `merge` and the CLI to this file.

- [ ] **Step 1: Write the seed master** `data/glossary.json`

```json
{
  "style": "al- (no sun-letter assimilation); ' for ayn/hamza; no macrons; first use: *translit* (ARABIC, english), short form after",
  "terms": {
    "التوحيد": {"translit": "tawhid", "english": "the Oneness of Allah"},
    "الشرك": {"translit": "shirk", "english": "associating partners with Allah"},
    "التزكية": {"translit": "tazkiyah", "english": "purification of the soul"},
    "الدعوة": {"translit": "da'wah", "english": "calling to Allah"},
    "الإصلاح": {"translit": "islah", "english": "reform"},
    "المصلح": {"translit": "muslih", "english": "the reformer"},
    "السنن الإلهية": {"translit": "al-sunan al-ilahiyyah", "english": "the divine norms — God's unchanging ways"},
    "التمكين": {"translit": "tamkin", "english": "empowerment; being established in the land"},
    "الوحي": {"translit": "wahy", "english": "revelation"},
    "الفتن": {"translit": "fitan", "english": "trials and tribulations"},
    "الاستقامة": {"translit": "istiqamah", "english": "uprightness"},
    "الغلو": {"translit": "ghuluww", "english": "extremism"},
    "الرِّبانية": {"translit": "rabbaniyyah", "english": "devotion to the Lord"},
    "العبودية": {"translit": "ubudiyyah", "english": "servitude to God"},
    "التجديد": {"translit": "tajdid", "english": "renewal"}
  },
  "names": {
    "النبي": "the Prophet ﷺ",
    "إبراهيم": "Ibrahim",
    "موسى": "Musa",
    "فرعون": "Pharaoh (Fir'awn)",
    "بنو إسرائيل": "the Children of Israel (Bani Isra'il)",
    "الصحابة": "the Companions",
    "الخلفاء الراشدون": "the Rightly-Guided Caliphs",
    "ابن تيمية": "Ibn Taymiyyah",
    "ابن القيم": "Ibn al-Qayyim",
    "السعدي": "al-Sa'di",
    "ابن عاشور": "Ibn 'Ashur"
  },
  "structure": {
    "القسم": "Part",
    "المبحث": "Chapter",
    "المطلب": "Section",
    "الفصل": "Chapter",
    "الباب": "Chapter"
  }
}
```

Also create `data/glossary-seed-notes.md` recording the two cross-book conflicts resolved by
editorial choice, for the user's later review: `التمكين` rendered "empowerment; being established
in the land" (Anwar used "empowerment", Bawsala "establishment" — merged both senses);
`السنن الإلهية` rendered "the divine norms" (Anwar "divine patterns", Bawsala "divine norms" —
chose "norms"). Note these can be changed later with `scripts/glossary.py merge` after sign-off.

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_glossary.py
import json

from scripts.glossary import load, diff


def _master():
    return {
        "style": "s",
        "terms": {"التزكية": {"translit": "tazkiyah", "english": "purification of the soul"}},
        "names": {"موسى": "Musa"},
        "structure": {"القسم": "Part"},
    }


def test_load_reads_json(tmp_path):
    p = tmp_path / "g.json"
    p.write_text(json.dumps(_master(), ensure_ascii=False), encoding="utf-8")
    assert load(str(p))["terms"]["التزكية"]["translit"] == "tazkiyah"


def test_diff_finds_new_entries_in_each_section():
    book = {
        "terms": {"التزكية": {"translit": "tazkiyah", "english": "purification of the soul"},
                  "الثغور": {"translit": "thughur", "english": "the frontiers"}},
        "names": {"موسى": "Musa", "نوح": "Nuh"},
        "structure": {"القسم": "Part", "المعلم": "Signpost"},
    }
    d = diff(_master(), book)
    assert d["new_terms"] == {"الثغور": {"translit": "thughur", "english": "the frontiers"}}
    assert d["new_names"] == {"نوح": "Nuh"}
    assert d["new_structure"] == {"المعلم": "Signpost"}
    assert d["conflicts"] == []


def test_diff_flags_conflict_without_override():
    book = {"terms": {"التزكية": {"translit": "tazkiyah", "english": "inner purification"}},
            "names": {}, "structure": {}}
    d = diff(_master(), book)
    assert len(d["conflicts"]) == 1
    c = d["conflicts"][0]
    assert c["section"] == "terms" and c["arabic"] == "التزكية"
    assert c["book"]["english"] == "inner purification"
    assert d["new_terms"] == {}


def test_diff_override_is_not_a_conflict_and_not_new():
    book = {"terms": {"التزكية": {"translit": "tazkiyah", "english": "inner purification",
                                   "override": "this book's preferred sense"}},
            "names": {}, "structure": {}}
    d = diff(_master(), book)
    assert d["conflicts"] == []
    assert d["new_terms"] == {}


def test_diff_ignores_book_metadata_block():
    book = {"book": {"title_en": "X"}, "terms": {}, "names": {}, "structure": {}}
    assert diff(_master(), book)["conflicts"] == []
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_glossary.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.glossary'`

- [ ] **Step 4: Write the implementation**

```python
# scripts/glossary.py
"""The master glossary and the per-book diff/merge tooling.

    python -m scripts.glossary diff  <book-glossary.json> [--master data/glossary.json]
    python -m scripts.glossary merge <book-glossary.json> [--master data/glossary.json]
                                     [--only <arabic,arabic,...>]

`diff` lists a book glossary's new entries and its conflicts against the master (for the harvest
step's review.md proposals). `merge` writes approved entries into the master AFTER the user has
signed off — never run it before sign-off. Stdlib only.
"""
import argparse
import json

SECTIONS = ("terms", "names", "structure")


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _entry_differs(master_val, book_val):
    # compare ignoring the book-only 'override' key
    if isinstance(book_val, dict):
        book_val = {k: v for k, v in book_val.items() if k != "override"}
    return master_val != book_val


def diff(master, book):
    out = {"new_terms": {}, "new_names": {}, "new_structure": {}, "conflicts": []}
    for section in SECTIONS:
        m = master.get(section, {})
        for arabic, book_val in (book.get(section, {}) or {}).items():
            has_override = isinstance(book_val, dict) and "override" in book_val
            if arabic not in m:
                if not has_override:
                    out["new_%s" % section][arabic] = book_val
            elif _entry_differs(m[arabic], book_val) and not has_override:
                out["conflicts"].append({
                    "section": section, "arabic": arabic,
                    "master": m[arabic], "book": book_val,
                    "override": None,
                })
    return out
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_glossary.py -v`
Expected: 5 passed

- [ ] **Step 6: Validate the seed file loads and is well-formed**

Run: `.venv/bin/python -c "from scripts.glossary import load; g=load('data/glossary.json'); print(len(g['terms']),'terms',len(g['names']),'names',len(g['structure']),'structure')"`
Expected: `15 terms 11 names 5 structure`

- [ ] **Step 7: Commit**

```bash
git add data/glossary.json data/glossary-seed-notes.md scripts/glossary.py tests/test_glossary.py
git commit -m "feat(glossary): seed master glossary + diff tooling"
```

---

### Task 2: `scripts/glossary.py` — merge + CLI

**Files:**
- Modify: `scripts/glossary.py` (add `merge`, `main`)
- Test: `tests/test_glossary.py` (append merge + CLI tests)

**Interfaces:**
- Consumes: `load`, `diff`, `SECTIONS` from Task 1.
- Produces: `merge(master: dict, book: dict, only: set|None = None) -> dict` — returns a NEW master dict with the book's new entries and overridden entries applied (never mutates the input); `only` restricts to those Arabic keys. Entries keep their `override` reason stripped when written to the master (the master holds canonical values, not per-book rationale). CLI subcommands `diff`/`merge` writing pretty JSON (`ensure_ascii=False, indent=2`).

- [ ] **Step 1: Append the failing tests**

```python
# append to tests/test_glossary.py
import subprocess
import sys

from scripts.glossary import merge


def test_merge_adds_new_terms_and_returns_new_object():
    master = _master()
    book = {"terms": {"الثغور": {"translit": "thughur", "english": "the frontiers"}},
            "names": {}, "structure": {}}
    merged = merge(master, book)
    assert "الثغور" in merged["terms"]
    assert "الثغور" not in master["terms"]          # input untouched


def test_merge_applies_override_and_strips_reason():
    master = _master()
    book = {"terms": {"التزكية": {"translit": "tazkiyah", "english": "inner purification",
                                   "override": "book sense"}},
            "names": {}, "structure": {}}
    merged = merge(master, book)
    assert merged["terms"]["التزكية"] == {"translit": "tazkiyah", "english": "inner purification"}


def test_merge_only_filter_restricts_keys():
    master = _master()
    book = {"terms": {"الثغور": {"translit": "thughur", "english": "the frontiers"},
                      "المحكمات": {"translit": "muhkamat", "english": "firm principles"}},
            "names": {}, "structure": {}}
    merged = merge(master, book, only={"الثغور"})
    assert "الثغور" in merged["terms"] and "المحكمات" not in merged["terms"]


def test_cli_diff_prints_new_and_conflicts(tmp_path):
    master_p = tmp_path / "master.json"
    master_p.write_text(json.dumps(_master(), ensure_ascii=False), encoding="utf-8")
    book_p = tmp_path / "book.json"
    book_p.write_text(json.dumps(
        {"terms": {"الثغور": {"translit": "thughur", "english": "the frontiers"}},
         "names": {}, "structure": {}}, ensure_ascii=False), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, "-m", "scripts.glossary", "diff", str(book_p), "--master", str(master_p)],
        capture_output=True, text=True)
    assert proc.returncode == 0
    assert "الثغور" in proc.stdout and "thughur" in proc.stdout


def test_cli_merge_writes_master(tmp_path):
    master_p = tmp_path / "master.json"
    master_p.write_text(json.dumps(_master(), ensure_ascii=False), encoding="utf-8")
    book_p = tmp_path / "book.json"
    book_p.write_text(json.dumps(
        {"terms": {"الثغور": {"translit": "thughur", "english": "the frontiers"}},
         "names": {}, "structure": {}}, ensure_ascii=False), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, "-m", "scripts.glossary", "merge", str(book_p), "--master", str(master_p)],
        capture_output=True, text=True)
    assert proc.returncode == 0
    written = json.loads(master_p.read_text(encoding="utf-8"))
    assert "الثغور" in written["terms"]
```

- [ ] **Step 2: Run to verify the new tests fail**

Run: `.venv/bin/python -m pytest tests/test_glossary.py -v`
Expected: Task-1 tests pass; new ones FAIL with `ImportError: cannot import name 'merge'`

- [ ] **Step 3: Append the implementation**

```python
# append to scripts/glossary.py
import copy


def _clean(val):
    if isinstance(val, dict):
        return {k: v for k, v in val.items() if k != "override"}
    return val


def merge(master, book, only=None):
    result = copy.deepcopy(master)
    for section in SECTIONS:
        dest = result.setdefault(section, {})
        for arabic, book_val in (book.get(section, {}) or {}).items():
            if only is not None and arabic not in only:
                continue
            clean = _clean(book_val)
            if arabic not in dest or dest[arabic] != clean:
                dest[arabic] = clean
    return result


def _write(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def main():
    ap = argparse.ArgumentParser(description="Master-glossary diff/merge (see module docstring).")
    ap.add_argument("command", choices=["diff", "merge"])
    ap.add_argument("book", help="the per-book glossary.json")
    ap.add_argument("--master", default="data/glossary.json")
    ap.add_argument("--only", default=None, help="merge: comma-separated Arabic keys to include")
    args = ap.parse_args()

    master, book = load(args.master), load(args.book)
    if args.command == "diff":
        print(json.dumps(diff(master, book), ensure_ascii=False, indent=2))
    else:
        only = set(args.only.split(",")) if args.only else None
        _write(args.master, merge(master, book, only=only))
        print("merged %s -> %s" % (args.book, args.master))


if __name__ == "__main__":
    main()
```

Note: move `import copy` up into the top import block with `argparse`/`json`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_glossary.py -v`
Expected: 10 passed

- [ ] **Step 5: Full suite**

Run: `.venv/bin/python -m pytest -m "not integration"`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add scripts/glossary.py tests/test_glossary.py
git commit -m "feat(glossary): merge + diff/merge CLI"
```

---

### Task 3: `out/assemble.py` — `--glossary` appendix

**Files:**
- Modify: `out/assemble.py` (add `append_glossary`, `glossary` param, `--glossary` arg)
- Test: `tests/test_assemble.py` (append glossary tests)

**Interfaces:**
- Consumes: `scripts.glossary.load` (for the CLI path).
- Produces: `append_glossary(book_md: str, glossary: dict) -> str` — appends a `## Glossary`
  section built from `glossary["terms"]` only, entries sorted by `translit` casefold, each as its
  own paragraph inside a `::: {.glossary}` fenced div, in the format
  `*translit* · [ARABIC]{lang=ar dir=rtl} · english`. Empty/absent terms → returns `book_md`
  unchanged (no empty section). `assemble(..., glossary=None)` calls it after the title block;
  `--glossary PATH` loads the file.

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_assemble.py
from out.assemble import append_glossary

_GLOSS = {
    "terms": {
        "التزكية": {"translit": "tazkiyah", "english": "purification of the soul"},
        "الإصلاح": {"translit": "islah", "english": "reform"},
    },
    "names": {"موسى": "Musa"},
    "structure": {"القسم": "Part"},
}


def test_append_glossary_adds_section_with_terms_sorted():
    out = append_glossary("# body\n\ntext", _GLOSS)
    assert "## Glossary" in out
    # sorted by translit casefold: islah before tazkiyah
    assert out.index("islah") < out.index("tazkiyah")
    assert "::: {.glossary}" in out


def test_append_glossary_entry_format():
    out = append_glossary("body", _GLOSS)
    assert "*tazkiyah* · [التزكية]{lang=ar dir=rtl} · purification of the soul" in out


def test_append_glossary_excludes_names_and_structure():
    out = append_glossary("body", _GLOSS)
    assert "Musa" not in out and "Part" not in out and "موسى" not in out


def test_append_glossary_empty_terms_is_noop():
    assert append_glossary("body", {"terms": {}, "names": {}, "structure": {}}) == "body"
    assert append_glossary("body", {}) == "body"
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_assemble.py -k glossary -v`
Expected: FAIL — `ImportError: cannot import name 'append_glossary'`

- [ ] **Step 3: Write the implementation**

```python
# add to out/assemble.py (near the other helpers)
def append_glossary(book_md, glossary):
    """Append a '## Glossary' section built from glossary['terms'] only, sorted by translit."""
    terms = (glossary or {}).get("terms") or {}
    if not terms:
        return book_md
    rows = sorted(terms.items(), key=lambda kv: kv[1]["translit"].casefold())
    entries = "\n\n".join(
        "*%s* · [%s]{lang=ar dir=rtl} · %s" % (v["translit"], ar, v["english"])
        for ar, v in rows)
    return "%s\n\n## Glossary\n\n::: {.glossary}\n%s\n:::\n" % (book_md, entries)
```

Wire into `assemble()` — after the title-block prepend, before writing:

```python
    if glossary:
        book = append_glossary(book, glossary)
```

Add the `glossary=None` parameter to `assemble(...)` and, in `__main__`, the arg + load:

```python
    p.add_argument("--glossary", help="path to the book's glossary.json (adds a Glossary appendix)")
    ...
    gloss = None
    if args.glossary:
        from scripts.glossary import load as _load_gloss
        gloss = _load_gloss(args.glossary)
    assemble(..., glossary=gloss)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_assemble.py -k glossary -v`
Expected: 4 passed

- [ ] **Step 5: Full assemble suite**

Run: `.venv/bin/python -m pytest tests/test_assemble.py -v`
Expected: all pass (existing + 4 new)

- [ ] **Step 6: Commit**

```bash
git add out/assemble.py tests/test_assemble.py
git commit -m "feat(assemble): --glossary appends a Glossary appendix (terms only)"
```

---

### Task 4: `out/convert.py` — Glossary + inline-Arabic CSS

**Files:**
- Modify: `out/convert.py` (extend `_HTML_CSS`)
- Test: none automated (CSS/rendering) — verified by screenshot in Step 3

**Interfaces:**
- Consumes: the `::: {.glossary}` div and `[…]{lang=ar dir=rtl}` spans that Task 3 emits.
- Produces: styled appendix + correctly-shaped inline Arabic in HTML.

- [ ] **Step 1: Add the CSS**

Append to `_HTML_CSS` (before the `@media print` block). The Glossary reuses the existing `h2`
chapter treatment automatically (it is an `h2`); this adds the entry list + inline-Arabic rule:

```css
/* ---- Inline Arabic inside English prose (glossary glosses, first-use terms) ---- */
[lang="ar"]{font-family:"Amiri","Amiri Quran",serif;font-size:1.06em}

/* ---- Glossary appendix: hanging-indent entries, no panel ---- */
.glossary{max-width:30em;margin:0 auto}
.glossary p{
  margin:.55rem 0;text-align:left;text-indent:0;
  padding-left:1.5em;text-indent:-1.5em;   /* hanging indent */
  line-height:1.5;
}
.glossary p em{font-style:italic;color:var(--ink)}
```

Also add to the `@media print` block so the appendix breaks onto its own page (it already does via
`h2{page-break-before:always}`, so no change needed there — verify in Step 3).

- [ ] **Step 2: Build a real book with the appendix**

Run (uses the completed alminhaj run + a converted glossary — the conversion is Task 6, so for
this step use the seed master as a stand-in glossary to exercise rendering):

```bash
.venv/bin/python -m out.assemble runs/alminhaj/work/translated /tmp/gloss-check.md \
  --title "Al-Minhaj" --author "Author" --no-hadith-numbers --glossary data/glossary.json
.venv/bin/python -m out.convert /tmp/gloss-check.md /tmp/gloss-check-out
```

Expected: no pandoc error; `/tmp/gloss-check-out/gloss-check.html` exists and contains a
`<div class="glossary">` and `<span lang="ar" dir="rtl">`.

Verify: `grep -c 'class="glossary"' /tmp/gloss-check-out/gloss-check.html` → `1`;
`grep -c 'lang="ar" dir="rtl"' /tmp/gloss-check-out/gloss-check.html` → ≥ 15.

- [ ] **Step 3: Screenshot-verify the rendering (impeccable: verify rendered output)**

Open the HTML headless at desktop + mobile widths and screenshot the Glossary page. Confirm:
Arabic glyphs shape and join correctly (not isolated/broken), each entry reads
`translit · ARABIC · english` on one hanging-indented line, the Arabic sits RTL without disturbing
the surrounding Latin order, and the page is legible in monochrome. Use whatever headless browser
is available (e.g. `chrome --headless --screenshot`). Record the screenshot path in the report.
If Arabic shaping is broken, the `[lang=ar]` font rule is the first suspect.

- [ ] **Step 4: Commit**

```bash
git add out/convert.py
git commit -m "feat(convert): Glossary appendix + inline-Arabic styling"
```

---

### Task 5: translator template + SKILL.md wiring

**Files:**
- Modify: `templates/translator-subagent.md` (first-use gloss format)
- Modify: `SKILL.md` (step 4 prime rewrite; new harvest step; `--glossary` on assemble)

**Interfaces:**
- Consumes: everything above (glossary schema, `scripts.glossary` CLI, `--glossary`).
- Produces: the documented prime → translate → harvest loop.

- [ ] **Step 1: Update the template's first-use rule**

In `templates/translator-subagent.md`, lane 1 (Author's prose), replace the gloss instruction
"Gloss a transliterated term on first use: *Tazkiyah (purification of the soul)*." with:

```markdown
   Gloss a transliterated term on FIRST use only, in this exact form:
   `*translit* ([ARABIC]{lang=ar dir=rtl}, english)` — e.g.
   `*tazkiyah* ([التزكية]{lang=ar dir=rtl}, purification of the soul)`. After the first use, write
   the short `*translit*` form alone. Take `translit`/`english` from the shared glossary's `terms`;
   do not invent your own rendering for a term the glossary already fixes.
```

Also in "House conventions" update the glossary bullet to say names come from `names`, recurring
terms from `terms`, and heading words from `structure`.

- [ ] **Step 2: Rewrite SKILL.md step 4 (Prime the glossary)**

Replace step 4 with:

```markdown
4. **Prime the glossary.** Copy the master to the book: `cp data/glossary.json <book>/work/glossary.json`.
   Add a `book` block (Arabic + English title/subtitle/author). Read ~3 spread-out chunks and ADD
   book-specific entries under `terms`/`names`/`structure` (keep the master's transliteration
   style). If this book deliberately renders a master term differently, add `"override": "<reason>"`
   to that entry — otherwise the harvest step will flag it as a conflict.
```

- [ ] **Step 3: Add `--glossary` to the assemble step**

In step 6 (Assemble), append `--glossary <book>/work/glossary.json` to the command and note it adds
the back-of-book Glossary appendix (terms only).

- [ ] **Step 4: Add the harvest step**

Insert a new step after Verify (renumber following steps):

```markdown
N. **Harvest the glossary.** `python -m scripts.glossary diff <book>/work/glossary.json` lists this
   book's new terms and any conflicts with the master. Write them into `<book>/work/review.md` under
   a "Glossary proposals" heading for the user's sign-off. After sign-off, run
   `python -m scripts.glossary merge <book>/work/glossary.json` (add `--only <keys>` to accept a
   subset) and commit the updated `data/glossary.json`. Never merge before sign-off.
```

- [ ] **Step 5: Re-read SKILL.md end-to-end**

Verify step numbering is consistent after the insertion, the assemble command shows `--glossary`,
and the harvest step references the same CLI Task 2 built.

- [ ] **Step 6: Commit**

```bash
git add templates/translator-subagent.md SKILL.md
git commit -m "docs(skill): prime-from-master + bilingual first-use + glossary harvest"
```

---

### Task 6: retrofit the existing books' appendix (operational)

**Files:**
- Create/convert: `runs/anwar/work/glossary.json`, `runs/alminhaj/work/glossary.json` (new schema; gitignored)
- Regenerate: each book's `output/book.{html,docx}`

**Interfaces:** consumes Tasks 3–4. No repo code changes; this is a data + build task.

- [ ] **Step 1: Convert each existing per-book glossary to the new schema**

For anwar and alminhaj, read the current `runs/<book>/work/glossary.json` and rewrite it in the new
schema: move heading words (Part/Chapter/Section/Signpost/Key/etc.) into `structure`; person/place
names into `names`; the remaining reader-facing terms into `terms` as `{translit, english}` (the
current values are `"Translit (english)"` or `"english (translit)"` — put the transliteration in
`translit` and the plain-English gloss in `english`). Keep the master's canonical rendering where a
term already exists in `data/glossary.json`; add `"override"` only where the book truly needs a
different sense. (Bawsala finishes in its current inline style — retrofit it after its run completes.)

- [ ] **Step 2: Re-assemble + convert each book with `--glossary`**

For each book, re-run the assemble command from its run (same `--title/--author/--no-hadith-numbers`
flags it originally used — see the book's review.md / project memory) adding
`--glossary runs/<book>/work/glossary.json`, then `python -m out.convert`.

- [ ] **Step 3: Screenshot-verify each book's Glossary page** (as Task 4 Step 3). Record paths.

- [ ] **Step 4: Report** the regenerated `output/book.html` paths and the glossary proposals (diff
vs master) for each book, for the user's sign-off. Do NOT merge into the master here without
sign-off. (No commit — `runs/` is gitignored.)
