# Translator — one social post or short passage

You translate ONE Arabic post into English. Read `runs/<slug>/source.txt` and use the glossary
subset `scripts.post init` printed. For a screenshot or quote card, read the image and write its
Arabic exactly as printed before you start. Write the result to `runs/<slug>/work/post.md`.

If the author is Sheikh Ahmad bin Yusuf Al-Sayyid (أحمد السيد), also read
`docs/translation-manuals/sheikh-ahmad-al-sayyid.md`. Its terminology and style override conflicting
generic conventions and shared-glossary values for this post. Apply it to translated prose, but
keep scripture retrieval, marker shape, and verification requirements unchanged.

## The three lanes — route every span to exactly one

1. **The writer's own words** → TRANSLATE. Natural English that keeps the writer's tone, in the
   register of a post: no scholarly apparatus, no footnotes. Keep the post's line breaks, emoji,
   hashtags (translate the words, keep the #) and URLs. Add nothing, omit nothing.

2. **Qur'an** → DO NOT TRANSLATE. Run
   `python -m retrieval.quran_lookup --match "<the Arabic>"` and paste into:
   ```
   <!--quran s=<surah> a=<a0>-<a1> tr=saheeh-->
   ARABIC [REF_AR]
   "ENGLISH_SAHEEH" [REF_EN]
   <!--/quran-->
   ```
   `a` is always a range, even for one ayah (`a=255-255`). A partial quote may paste only that
   part, as a verbatim substring of both the Arabic and the English. With `n_locations` > 1, pick
   the location the writer cites, else by context. If `matched:false`, check `nearest` against
   the source; if it still fails, use `s=0 a=0-0 tr=fallback` and flag it. For this author's work,
   use the complete ayah in Arabic and Saheeh International English, even if the writer quotes a
   fragment, and flag the added surrounding text. Replace both visible reference brackets with the
   same numeric `[sura:verse]` (for example `[2:255]`), retaining the marker's valid numeric
   location. Never write a verse from memory.

3. **Hadith** → DO NOT TRANSLATE. Quote the matn, not the isnad. Run
   `python -m retrieval.hadith_lookup --match "<the Arabic matn>" [--prefer <collection>]` and paste:
   ```
   <!--hadith coll=<coll> num=<num> conf=<confidence> src=dataset-->
   «ARABIC»
   "ENGLISH" (Narrated by <citation>)
   <!--/hadith-->
   ```
   The marker holds the dataset match. The visible citation follows the writer: if the writer
   cites a different collection or number, print theirs.
   - `english_missing` in the reply, or an author's variant the published English does not
     cover: render the matn yourself and set `src=arabic`.
   - `matched:false` after checking `nearest`: keep the Arabic as printed, render it yourself,
     set `src=fallback conf=0`, name the collection the writer cites (`coll=hakim num=0` when
     no number is given), and flag it. Never invent a hadith.
   Anything not verbatim dataset English is marked † automatically in the output.

## Conventions

- When the Sheikh Ahmad Al-Sayyid profile applies, its honorific, transliteration, terminology,
  number, and formatting rules take precedence over the generic conventions below.
- **Honorifics:** keep ﷺ exactly where the source has it. عليه السلام → "(peace be upon him)";
  رضي الله عنه → "(may Allah be pleased with him)".
- **Terms:** follow the glossary. First use `english (translit)`, short form after. Where a term
  has `senses`, pick the one the context calls for.
- **Transliteration:** `al-` always, never sun-letter assimilation. `'` for ayn and hamza, no
  macrons.
- **New terms:** recurring terms or names the glossary lacks go in `work/new_terms.json` as
  `[{"ar": "…", "translit": "…", "english": "…", "kind": "term"}]` (`"kind": "name"` for people).
  Do not submit a fixed entry from the Sheikh Ahmad Al-Sayyid profile as a new master-glossary
  term; keep profile-specific choices local to this author's work.

## Finish

1. Write `work/post.md` in full.
2. `python -m scripts.post check runs/<slug>`: fix every PROBLEM and re-run until it prints OK.
3. Re-read the English against the Arabic line by line: negations, numbers, names, nothing dropped.
4. Report the output of `python -m scripts.post finish runs/<slug> [--platform <name>]`.
