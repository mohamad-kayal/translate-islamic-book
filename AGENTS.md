# Instructions for any agent working in this repo

This tool translates Arabic Islamic material into English: books (PDF), lectures (YouTube or
SRT/VTT) and social posts. It was built on Claude Code and runs the same on any agent that can run
shell commands, read and write files, and view images. These rules apply to every model, so a run
produces the same quality of result whichever agent does it.

## What never changes

1. **Scripture is retrieved, never written.** Every quoted verse and hadith comes from
   `retrieval.quran_lookup` or `retrieval.hadith_lookup`. Never write one from memory, never
   "improve" its wording, and never translate it yourself unless the template sends you down the
   flagged fallback path.
2. **Your own judgment does not finish a run.** A run is finished when
   `python -m scripts.gate runs/<slug>` exits 0. If it fails, fix what it names. Never say a run is
   done, or that scripture is verified, while it fails.
3. **Report what is flagged.** † hadith, fallbacks, variants and held glossary conflicts go to the
   user in plain words. A clean-looking output with hidden doubts is a failure.
4. **Citations follow the author; wording follows the dataset.**
5. **Sign-off belongs to the user.** Do not edit `data/english-fixes.json`, resolve a glossary
   conflict, or alter a `review.md` without it. Do not `git push`.

## Setup

```bash
./install.sh                     # venv, pinned datasets, skill links, then runs doctor
.venv/bin/python -m scripts.doctor   # re-check any time; READY means a run can start
```

Run every command from this folder. `python` below means `.venv/bin/python`.

## Pick the job

| The user has | Follow |
|---|---|
| An Arabic book PDF | `skills/translate-islamic-book/SKILL.md` |
| A YouTube link, or an Arabic `.srt`/`.vtt` | `skills/translate-srt/SKILL.md` |
| A post, quote card, link to a post, or a few paragraphs | `skills/translate-post/SKILL.md` |

Read the whole SKILL.md and follow its steps in order. Do not skip the pilot, the reviser pass or
the gate because the job looks easy. The briefs in `templates/` are binding for whoever does the
translating, you included.

## Where the skills mention a Claude Code feature

| The skill says | On your agent |
|---|---|
| `${CLAUDE_SKILL_DIR}` | This repo. Just work from this folder. |
| Dispatch a subagent | Use your agent's subagent or task feature if it has one, giving each subagent only the one-line brief the skill shows. If it has none, do the units yourself one at a time. |
| Parallel waves | Run units one after another if you cannot run them in parallel. Slower, same result. Check `python -m scripts.run_status <work>` to see what is left. |
| Workflow, `.claude/workflows/` | Claude Code only. Do the same loop by hand: translate, check, revise, retry a failed unit once. |
| Usage gate, `--gate`, statusline | Claude Code only. Skip it; `run_status` without `--gate` works everywhere. |
| An independent reviser | Keep it independent: use a separate agent or a fresh session that has not seen the translation being made. If you truly cannot, re-read the source pages from scratch and say in `review.md` that the translator revised its own work. |

Doing units yourself, one at a time: re-read the template before each one, keep only that unit's
pages in mind, and write the unit's file before moving on. Every file on disk survives a restart, so
never hold finished work only in your reply.

## Reading Arabic pages

Book translation reads page images, because Arabic text layers are often garbled and Qur'anic fonts
extract as nonsense.

```bash
pdftoppm -r 150 -f <page> -l <page> -png <book.pdf> /tmp/page
```

Open the PNG with your image tool and read the Arabic as printed. If your agent cannot view images,
do not translate a book from `pdftotext` output and hope: stop and tell the user this agent cannot do
the job faithfully. A misread word in a verse fails the lookup; a misread word in prose fails
silently.

## Choosing models

Translation is where quality is decided, so use the most capable model you have, with its thinking
turned up. Revising is mostly reading, so a mid-tier model is fine. A model weak at classical Arabic
will still pass the scripture checks, because those test the datasets, not the prose. Pilot the
first unit and read it critically before committing to the rest.

## Layout

```
skills/      one SKILL.md per format: the steps
templates/   the briefs: book-*, lecture-*, post-translator
retrieval/   shared lookups, glossary, verbatim comparison
ingest/ out/ book pipeline
subs/        lecture pipeline
scripts/     every CLI: gate, doctor, run_status, glossary, finish_*, post, ingest_*
data/        master glossary, series notes, pinned datasets (downloaded, never committed)
editor/      local web app for proofing subtitles
runs/        one folder per job, never committed
```

Tests: `python -m pytest -q`. They must stay green.
