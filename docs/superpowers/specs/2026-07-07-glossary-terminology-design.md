# Master glossary + bilingual terminology — design

Date: 2026-07-07 · Status: approved in brainstorm (inline + appendix; appendix retrofit; approval-gated harvest)

## Problem

Every book's glossary is primed from scratch (SKILL.md step 4), so renderings drift across books —
already observed between Al-Minhaj and Bawsala: التزكية "Tazkiyah (purification of the soul)" vs
"inner purification (tazkiyah)"; التمكين "empowerment (tamkin)" vs "establishment (tamkin)";
السنن الإلهية "divine patterns" vs "divine norms". And the finished English books never show the
Arabic script of a term, though the readership benefits from seeing it. Goal: terminology that is
consistent across all books and improves with each one — data compounds in a glossary, with the
user's sign-off, no self-modifying automation — and a reader-facing bilingual treatment.

## Decisions (locked)

1. **Inline + appendix.** First use per book: `*tazkiyah* (التزكية, purification of the soul)`;
   later uses use the short form. Every book gains a back-of-book Glossary appendix.
2. **Appendix retrofit** for the three existing books (re-run assemble+convert only — no
   re-translation). Inline Arabic starts with the next new book; Bawsala finishes in its current
   inline style so no book mixes styles.
3. **Approval-gated harvest.** New terms/conflicts are proposed in review.md; only after the
   user's sign-off are they merged into the master and committed. No LESSONS.md, no auto-learning:
   rules keep being baked into SKILL.md/template by hand, as is already the practice.
4. **Transliteration house style unchanged**: `al-` (no sun-letter assimilation), `'` for
   ʿayn/hamza, no macrons — matching the three published books.

## Components

### `data/glossary.json` — the master (committed, versioned)

```json
{
  "style": "al-, no assimilation; ' for ayn/hamza; no macrons; first-use gloss: *translit* (ARABIC, english)",
  "terms":     { "التزكية": {"translit": "tazkiyah", "english": "purification of the soul"} },
  "names":     { "إبراهيم": "Ibrahim" },
  "structure": { "القسم": "Part" }
}
```

- `terms` — reader-facing: get the inline first-use gloss and appear in the appendix.
- `names` — people/works: consistency only, never in the appendix.
- `structure` — heading words (القسم → "Part") that parallel chunks must not drift on; never in
  the appendix. (Bawsala's current file mixes these into terms; the schema split fixes that.)
- Seeded from the three existing runs' glossaries. Seeding surfaces the known conflicts (tamkin,
  sunan, tazkiyah phrasing, …) for a one-time user ruling; that ruling happens during
  implementation, not in this spec.

### Per-book `work/glossary.json`

Same schema plus the `book` block (title/subtitle/author, Arabic + English — as Bawsala
pioneered). SKILL.md step 4 becomes: copy the master; read ~3 spread-out chunks; ADD book-specific
entries. A deliberate deviation from the master must carry `"override": "<reason>"` — silent drift
becomes impossible.

### `scripts/glossary.py` — diff/merge utility (~80 lines, tested)

- `diff <book-glossary>`: entries new vs master; entries conflicting with master (same Arabic key,
  different rendering, no override) → JSON + human summary. Feeds the review.md proposals.
- `merge <book-glossary> [--only k1,k2,…]`: write approved entries into `data/glossary.json`
  (sorted, stable formatting). Exists so nobody hand-edits Arabic JSON keys.

### Template edit (`templates/translator-subagent.md`)

First-use gloss format becomes `*translit* (ARABIC, english)` sourced from the glossary's
`translit`/`english` fields; later uses short form. Subagent mechanics otherwise unchanged.

### Output: `out.assemble --glossary <path>` + convert

- Assemble appends a `## Glossary` appendix to book.md: `terms` only, sorted by transliteration,
  one hanging-indent entry per line — *tazkiyah* · التزكية · purification of the soul. No boxes,
  no table grid (PRODUCT.md: distinguished by setting).
- Convert gives it the appendix/chapter treatment (own page in print).
- **Verified-glyph risk:** inline Arabic inside English paragraphs is new for convert. Body font
  Cardo has no Arabic glyphs — needs font fallback to Amiri plus `lang="ar" dir="rtl"` spans, and
  a rendered screenshot check before shipping (PRODUCT.md principle 4). Same applies to the
  appendix's Arabic column.

### SKILL.md changes

- Step 4 (prime) rewritten as above.
- New harvest step after verify: run `scripts/glossary.py diff`, write a "Glossary proposals"
  section into review.md (new terms + conflicts), and after the user's sign-off run `merge` and
  commit the master. Nothing merges without sign-off.
- Assemble step gains `--glossary <book>/work/glossary.json`.

## Flow

Prime (master copy + book additions) → subagents translate with glossary → verify → harvest diff
→ review.md proposals → user sign-off → merge + commit master → assemble with `--glossary` →
appendix in the book. Next book starts from a richer master.

## Rollout (one-off, part of the implementation plan)

1. Seed the master from the three runs (user resolves conflicts).
2. Convert the three per-book glossaries to the new schema.
3. Re-run assemble+convert for anwar and alminhaj (and bawsala when its run completes) with
   `--glossary` → all gain the appendix. Screenshot-verify the appendix rendering.

## Testing

- `glossary.py` diff/merge units: new keys, conflicts, override suppression, `--only` filter,
  stable output ordering.
- Assemble: appendix from a fixture glossary (terms only; names/structure excluded; sort order).
- Schema round-trip on the three real glossary files.
- Rendered screenshot check: appendix page + inline Arabic in an English paragraph (font
  fallback, shaping, direction).

## Out of scope (deliberate, YAGNI)

- Macron/ALA-LC transliteration change.
- Per-chapter re-glossing (first use per book only).
- Names index and the Quran/hadith citation index (queued with the design + cover session).
- Any automation that edits SKILL.md or merges glossary entries without user sign-off.
