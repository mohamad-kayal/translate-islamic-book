# Translation and transliteration profile: Sheikh Ahmad Al-Sayyid

This profile consolidates the user-provided *Translation & Transliteration Manual: Sheikh Ahmad
Al-Sayed’s Works* for use by this repository's translation workflows.

## Scope and precedence

Apply this profile to work written, delivered, or authored by Sheikh Ahmad bin Yusuf Al-Sayyid
(أحمد السيد), including books, lectures, posts, and material explicitly attributed to him. Confirm
the author or speaker from the source or the user's instructions; if attribution is uncertain, ask
or flag it rather than assuming.

For his work, this profile takes precedence over conflicting generic house style, series notes, and
the shared glossary. Apply author-specific terminology in the run; do not change the shared
glossary merely to satisfy this profile. Preserve the pipeline's retrieval, marker, timing, and
verification requirements. Never alter dataset-sourced sacred text to make it fit a style rule.

## Fixed terminology

| Arabic | Required English |
|---|---|
| أحمد السيد | Ahmad bin Yusuf Al-Sayyid |
| مرجعية الوحي | the revelational authority |
| الوحي | the revelation (always with the definite article) |
| مركزي | central; a central issue (as context requires) |
| مركزة المركزيات | prioritizing priorities |
| السنن الإلهية | the divine universal laws |
| الجيل الصاعد | the rising generation |
| صناعة المصلحين | the building of reformers |
| البناء | development |
| العطاء | active contribution |
| التدريب العطائي | training for active contribution |
| المحكمات | explicit |
| المتشابهات | ambiguous |
| الرباني | Rabbani |
| فقه الأولويات | understanding of priorities |
| التجارب الإصلاحية | reformative endeavors |
| التيارات | movements |
| الثقافة المعيارية لدى المصلحين | ethos |
| المنهج الإصلاحي | reform methodology |
| التنزيل على الواقع | application in reality |
| مبدأ التدرج | gradualism |
| الورع | conscientiousness |
| المرحلة | the current stage |

| Arabic title | Required English title |
|---|---|
| بوصلة المصلح | *The Reformer’s Compass* |
| خارطة الثغور | *The Map of Frontlines* |
| سبيل المصلحات | *The Path to Restoring the Role of the Muslim Woman* |
| المنهاج من ميراث النبوة | *Al-Minhaj: The Clear Path from the Heritage of Prophethood* |
| القبس الوهاج في تلخيص شرح المنهاج | *Al-Qabas al-Wahhaj: A Summary of the Explanation of al-Minhaj* |
| سوية المؤمن | *The Believer’s Psychological Soundness* |
| السنن الإلهية وأثرها في فهم الواقع والعمل الإصلاحي | *The Universal Divine Laws and Their Impact on Understanding Reality and Reform* |
| السنن الإلهية وأثرها في الإصلاح | *The Universal Divine Laws and Their Impact on Reform* |
| أنوار الأنبياء | *The Prophetic Blueprint for Reform* |
| معالجة القرآن لنفوس المصلحين | *The Qur’an Healing the Souls of the Reformers* |
| السيرة النبوية للمصلحين | *The Sirah for Reformers* |
| مركزيات الإصلاح | *The Priorities of Reform* |

In book-format output, on the first occurrence of **مرجعية الوحي**, add a brief explanatory
footnote: “Meaning the Qur’an and Sunnah as the ultimate reference point.” Do not repeat it at later
occurrences. In a format that cannot carry footnotes, flag the requested note for the user rather
than adding scholarly apparatus to the text.

When the author-specific translation conflicts with a shared-glossary value, use the translation
above for this author's work and record the choice in the run's `DISPATCH.md` or run-local glossary.
Use the transliteration rules below for any accompanying Arabic transliteration.
The no-diacritics rule for proper names and book titles takes precedence over any diacritic shown
in a title example in the source manual (for example, write *al-Wahhaj*, not *al-Wahhāj*).

## Transliteration

- Use ʿ (ayn) and ʾ (hamza), never apostrophes or quotation marks for those letters. Drop an
  initial hamza.
- Proper names (people, places, dynasties, institutions, organizations, and book titles) take no
  macrons or underdots; retain ʿ and ʾ. Do not italicize personal or other proper names.
- Use established English spellings for place names and modern figures who use a Latin spelling of
  their own name. Otherwise transliterate personal and historical names without macrons or
  underdots.
- Transliterate prophets and historical figures without an established English spelling (for
  example, Musa, Isa, Uthman, and Ibn Khaldun).
- Use full diacritics only for transliterated common or technical terms not listed in
  Webster’s/Merriam-Webster. Anglicized dictionary words (for example, Quran, hadith, sharia,
  Sunni, Muslim, Mecca, Medina, jihad, ulama, imam, and fatwa) take no diacritics or italics,
  except where the IJMES Word List explicitly prescribes otherwise.
- Follow the IJMES transliteration chart and word list for letter forms and listed exceptions:
  <https://www.cambridge.org/core/services/aop-file-manager/file/57d9042c58fb76353506c8e7/IJMES-Word-List-Updated-August-8-2026.pdf>.
- Write tāʾ marbūṭa as `a`, or `at` in construct; double doubled consonants; use `-i` for nisba
  and `-iyya` for feminine/abstract endings (for example, *madrasa*, *Madrasat al-Hayah*,
  *Misri*, and *ʿArabiyya*). Add a roman `s` to transliterated plurals where natural.
- Write the definite article as `al-`, never assimilated to a sun letter. Use lowercase `al-`
  mid-sentence, capitalize the following proper noun, and capitalize `Al-` at sentence start.
- Spell out `Ibn`; use `b.` for `son of` and `bt.` for `bint` in genealogical chains. Write
  compounds such as Abu Bakr, Umm Kulthum, and ʿAbd al-Rahman consistently.
- Italicize transliterated common terms not in Webster’s; do not italicize proper names.
  Transliterate book titles in italics without macrons or underdots, retaining ʿ and ʾ. On first
  mention, follow the transliteration with the English translation in parentheses, in roman type.
  Use the established English title for well-known works, giving the transliterated form once.
- In Arabic title transliterations, capitalize the first word and proper nouns only.
- Translate poetry and Qur’anic meaning into English, while applying the sacred-text rules below
  to Qur’anic quotations.
- Flag any uncertain term or name rather than silently choosing a form.

## Formatting and numbers

- Use American spelling, serial commas, and Chicago punctuation. Use en dashes for ranges.
- Italicize book, periodical, and newspaper titles. Keep chapter/article titles and unpublished
  works in roman type and enclose them in double quotation marks.
- Spell out numbers below one hundred. Use numerals for larger numbers, dates, percentages, and
  page references. Preserve required numerals in scripture citations, hadith references, metadata,
  subtitle timing, and other machine-checked fields.
- Give dates in CE by default. On first mention, give Hijri dates as `AH 656/1258 CE`; use the
  established form consistently thereafter.
- Cite Qur’anic verses numerically as `[sura:verse]` (for example, `[2:255]`), using an en dash
  for a verse range.

## Honorifics

- For honorifics paired with Allah (for example, سبحانه وتعالى and جل جلاله), use “Almighty” or
  “the Almighty”; for example, “Allah the Almighty.”
- Translate other honorific formulas and put them in parentheses: “Muhammad (peace and blessings
  be upon him),” “Musa (peace be upon him),” “Uthman (may Allah be pleased with him),” and
  “Sufyan al-Thawri (may Allah have mercy on him).”
- If the name is already inside the author's parentheses, do not nest parentheses; join the
  honorific with a comma, as in “the Prophet, peace and blessings be upon him.”
- These rendering rules apply to translated prose and lead-ins, not to dataset-sourced Qur’an or
  hadith text, which must remain verbatim.

## Qur’anic quotations and translator’s notes

- Use only the exact Saheeh International English translation. Retrieve it from the project's
  dataset; never substitute, blend, paraphrase, shorten, or “improve” it.
- Use the complete retrieved ayah in both Arabic and English. If the source quotes only a fragment,
  include the full ayah and flag that the surrounding words were supplied to satisfy the manual.
  In lecture subtitles, retain the spoken segment ranges and timestamps; flag any resulting
  subtitle-length or timing concern rather than trimming the verse.
- If the exact wording cannot be confirmed, do not guess. Flag the reference as
  `[VERIFY: 2:255, Saheeh International text needed]` and add it to the translator’s queries.
  The run remains subject to the normal verification gate.
- If the author’s argument relies on an Arabic word, root, grammatical form, or wording not
  apparent in Saheeh International, leave the verse unchanged and add a concise footnote beginning
  `[Translator’s Note]`. Give the relevant Arabic phrase in transliteration and its meaning, explain
  briefly how the published English obscures the link, and state only the connection the author
  makes. Do not add independent exegesis or opinion.
- Do not add scholarly footnotes to a format that cannot carry them, such as subtitle cues or a
  social post; flag a necessary explanation for the user instead.
