# Series notes — أنوار السنة المحمدية | رياض الصالحين (runs `riyad-NN`)

Read at Prime (SKILL.md step 2) and fold into `DISPATCH.md`; update at Finish with anything
the new episode established. These are conventions the glossary can't carry — renderings we
coined, series facts, and how the room behaves.

- **Speaker:** Ahmad al-Sayyid (أحمد السيد) — same author as the translate-islamic-book
  master glossary and the `sirah` series, so his terminology is already well covered there.
- **Series title:** أنوار السنة المحمدية — a running commentary on Imam al-Nawawi's hadith
  anthology *Riyad al-Salihin*. Render the series title as "The Lights of the Muhammadan
  Sunnah (Anwar al-Sunnah al-Muhammadiyyah)" (ours; no published English title known).
- **The book:** رياض الصالحين of Imam al-Nawawi (الإمام النووي, d. 676 AH) →
  **"Riyad al-Salihin (The Gardens of the Righteous)"** first use, "Riyad al-Salihin" after.
  The author is **"Imam al-Nawawi"**.
- **Format:** live class, hadith-by-hadith. Each session works through one or more of
  al-Nawawi's *chapters* (باب): the speaker reads al-Nawawi's chapter heading, then the
  Qur'anic verses al-Nawawi cites under it, then each hadith (with its takhrij — "متفق عليه",
  "رواه البخاري", etc.), then explains. **Scripture is dense here — retrieval is the whole
  game**; verses and hadith matns must come from the datasets, never memory.
- **Chapters (باب):** render as "the chapter on X (Bab …)" — e.g. باب الإخلاص والنية →
  "the chapter on Sincerity and Intention (Bab al-Ikhlas wa'l-Niyyah)"; باب التوبة →
  "the chapter on Repentance (Bab al-Tawbah)"; باب الصبر → "the chapter on Patience
  (Bab al-Sabr)". Short form "the chapter on Patience" after first use.
- **Session openings:** each lecture opens with the khutbat al-hajah (praise of Allah +
  salawat "اللهم صل على محمد…"). Treat the formulaic praise/salawat as prose; only an
  actual recited verse inside it gets retrieved.
- **al-Nawawi's numbering:** he numbers hadith in his own sequence. Cite each hadith by its
  ORIGINAL collection via `hadith_lookup` (bukhari/muslim/…), not by a Riyad al-Salihin number.
- **Numbers:** digits, not words.

## Episodes

- `riyad-01` (2026-07-16) — باب الإخلاص والنية (Sincerity & Intention), part 1;
  opening of the series. 25 blocks, 71.6 min, 0 majors, 55 minor fixes.
  Scripture: 7 quran + 25 hadith, 0 fallbacks. Glossary → 107 names / 112 terms.
  NB: first run through the json3 URL ingest path — exposed + fixed a rolling-overlap
  timing bug in `words_from_json3` (YouTube auto-caption events overlap; ends now clamp to
  the next word's start). `ingest_video` also pinned to yt-dlp's android player client
  (the default web client is PO-token-gated). Both fixes apply to every later episode.
- `riyad-02` — باب الإخلاص والنية part 2 (Sincerity and Intention (Bab al-Ikhlas wa'l-Niyyah)).
- `riyad-03` — باب التوبة part 1 (Repentance (Bab al-Tawbah)).
- `riyad-04` — باب التوبة part 2 (Repentance (Bab al-Tawbah)).
- `riyad-05` — باب التوبة part 3 (Repentance (Bab al-Tawbah)).
- `riyad-06` — باب الصبر part 1 (Patience (Bab al-Sabr)).
