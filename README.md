# SRT-translator

A Claude Code skill that translates Arabic Islamic-lecture YouTube auto-captions into
publication-quality English subtitles — plus a growing shared glossary and (coming) a
mobile-first SRT editor web app.

Built on the architecture proven by
[translate-islamic-book](https://github.com/mohamad-kayal/translate-islamic-book):
sacred text is retrieved verbatim from bundled datasets, never model-written; parallel
subagents do the linguistics; deterministic Python does everything checkable.

## How it works

```
YT auto-captions (URL via yt-dlp json3, or .srt/.vtt file)
  → word timeline           (rolling-caption overlaps flattened, per-word times)
  → proto-segments          (pause-based anchor units — mechanical, no linguistics)
  → ~3-min blocks           (+ previous-tail context)
  → translator subagents    (sentence grouping, translation, |-marked break points,
                             Qur'an/hadith retrieved verbatim, condensing, new terms)
  → retime (pure Python)    (cue splits at the marks, char-proportional timing,
                             ≤42 chars × 2 lines, ≤20 cps, 0.8–7 s — model never sees a timestamp)
  → reviser subagents → lint → glossary harvest → .en.srt + review.md + bilingual.md
```

The **live glossary** (`data/glossary.json`) grows on every run: brand-new terms auto-merge
(logged in `data/glossary-changelog.md`, one git commit per run); changed renderings of
existing terms are held in `review.md` until accepted with
`python -m scripts.glossary resolve <run> --accept <terms>`.

## Usage

See `SKILL.md` (the pipeline the orchestrating agent runs). Quick start:

```
python3 -m venv .venv && .venv/bin/pip install pytest
.venv/bin/python -m scripts.setup_data
.venv/bin/python -m scripts.ingest_video <url-or-srt> --run runs/<slug>
# then follow SKILL.md steps 2–8 (pilot → waves → revise → finish)
```

## Layout

`subs/` pipeline package · `scripts/` CLIs · `retrieval/` Qur'an+hadith lookup (vendored) ·
`templates/` subagent briefs · `data/` glossary + datasets · `tests/` pytest ·
`editor/` mobile SRT editor (sub-project, spec in `docs/superpowers/specs/`).

## License

MIT for the code. Datasets (fawazahmed0 quran/hadith APIs) and any translated lecture content
carry their own rights.
