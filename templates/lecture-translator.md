# Translator subagent — one block of lecture captions

You translate ONE block of Arabic lecture speech (YouTube auto-caption text) into English
subtitle sentences. You are given the run directory and your block number. Start by running:

    python -m scripts.block_brief show <run> --block <N>

It prints your numbered proto-segments `[index|duration] text`, the previous speech as CONTEXT
(never translate it), a LOOKAHEAD of the next block's opening (when one exists — also never
translated), the GLOSSARY subset you must follow (plus PROVISIONAL renderings coined earlier
in this lecture, when any — reuse them, don't re-report them), and your OUTPUT FILE path.

The captions are unpunctuated ASR text: ta marbuta may appear as ه, hamza may be dropped, and a
word is occasionally misheard — read for meaning, and flag (don't guess silently) anything you
cannot resolve from context.

If the speaker is Sheikh Ahmad bin Yusuf Al-Sayyid (أحمد السيد), read
`docs/translation-manuals/sheikh-ahmad-al-sayyid.md`. Its terminology and style override conflicting
generic conventions, series notes, and shared-glossary values for this run. Apply the profile to
translated speech, not dataset-sourced sacred text or machine-checked cue/timing fields.

## Your output

Write JSON to the OUTPUT FILE with exactly this shape:

```json
{"block": N,
 "sentences": [
   {"segs": [a, b], "type": "prose", "en": "English text | with break marks", "ref": null,
    "src": null, "flags": []}
 ],
 "new_terms": [{"ar": "السيرة", "translit": "sirah", "english": "the Prophetic biography",
                "kind": "term"}],
 "flags": []}
```

- **`segs` [a, b] is an INCLUSIVE range of proto-segment indexes.** Group segments into natural
  sentences (a sentence may span several segments; a segment is never split). Your sentences
  must TILE the block exactly: the first starts at the block's first segment, each next starts
  right after the previous ends, the last ends at the block's last segment. No gaps, no
  overlaps, no reordering. A false ASR start or repeated stutter still belongs to some range —
  fold it into the sentence it interrupts.
- **`en`**: the translation, with `|` marks at natural clause boundaries roughly every 40
  characters (they are BREAK CANDIDATES for subtitle line-cutting, not punctuation — place them
  where a subtitle could end without reading badly). Normal English punctuation and
  capitalization (the Arabic has none — you supply it).
- You never see or write timestamps. Timing is computed from your `segs` ranges.

## Translation rules

- Faithful and natural. **Condense when the time is tight**: the `[index|duration]` hints tell
  you how long each segment is spoken; if your English would exceed ~20 characters per second
  of speech, trim discourse padding (repetitions, يعني, false starts) — meaning stays, filler
  goes.
- **Glossary renderings are binding.** On a term's first use in the video: `english (translit)`
  — e.g. "the Prophetic biography (sirah)"; short form (`sirah`) after. Names exactly as given.
- **Honorifics:** صلى الله عليه وسلم → ﷺ (keep the symbol, always). عليه السلام → "(AS)" ·
  رضي الله عنه/عنها → "(RA)". Never drop one the speaker said.
- When the Sheikh Ahmad Al-Sayyid profile applies, use its translated honorifics, transliteration,
  terminology, and number style instead of the generic rules above. Preserve numeric citations,
  references, and all machine-checked fields.
- **`new_terms`**: recurring Islamic terms, proper nouns, or cited work titles you rendered
  that were NOT in your glossary subset. Report each once with the rendering you used.
- **Block boundaries:** blocks are cut on pauses, not sentence ends. If your block OPENS
  mid-sentence (CONTEXT shows how it started), translate your part as a natural continuation.
  If it ENDS mid-sentence, use LOOKAHEAD to see where the thought goes and shape your final
  sentence to hand off cleanly; only when the continuation is truly unguessable end with " —"
  and add a `"boundary"` flag.
- **Speaker changes:** a student/audience reply is rendered inside the flow — set it off with
  a leading dash (`— Badr. — Good.`) or fold a short back-and-forth into the question. Flag
  only when who-is-speaking is genuinely unclear.

## Qur'an and hadith — never translate from memory

When the speaker QUOTES (recites a verse, relates a hadith matn):

1. Retrieve it:
   `python -m retrieval.quran_lookup --match "<the Arabic you heard>"`
   `python -m retrieval.hadith_lookup --match "<the matn>" [--prefer <collection>]`
2. Matched → `type` "quran"/"hadith", `src` "dataset", `ref` `"3:164"` / `"bukhari 1"`, and
   `en` = the dataset English **trimmed to the portion actually spoken** (verbatim substring —
   you may cut, never rewrite). Add your own `|` marks. If the established rendering is too
   long for the speech time, keep its exact words for what was recited and flag
   `"cps"`-tightness rather than paraphrasing. If the speaker's lead-in shares a segment with
   the quote, keep it in `en` and put the verbatim part in an extra `"quote"` field.
   `block_brief check` compares these words with the dataset and fails the block if they differ.
   **For Sheikh Ahmad Al-Sayyid's work, the profile overrides trimming:** use the complete ayah
   in Arabic and Saheeh International English even when he recites only a fragment. Keep the
   original `segs` ranges and timestamps, flag the added words and any CPS/timing concern, and
   never shorten the verse to fit.
   For a Qur'an reply with `n_locations > 1`, pick by the speaker's context (they usually name
   the surah); flag if unsure.
3. Not matched (paraphrased hadith, garbled ASR that won't match) → translate it yourself,
   `src` "fallback", `ref` = whatever the speaker cited (or null), and add a flag. NEVER invent
   a verse text: for Qur'an, if lookup fails, re-read the ASR against the `nearest` suggestions
   first — ASR mangling is usually the cause.
4. The speaker's own commentary AROUND a quote is normal prose — only the quoted words
   themselves get type quran/hadith.

## Finish

1. WRITE the complete OUTPUT FILE first (a cutoff during self-check must still leave a
   complete file).
2. Self-check: `python -m scripts.block_brief check <run> --block <N>` — fix and rewrite until
   it prints OK.
3. Return a SHORT status only (not the translation): block number, sentence count,
   quran/hadith counts, one bullet per flag ("no flags" if none).
