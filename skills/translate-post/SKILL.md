---
name: translate-post
description: Translate an Arabic Islamic social post or short passage into English, with any quoted
  Quran or hadith retrieved verbatim from reference datasets and machine-checked, ready to post.
  Use when the user gives a Facebook, X, Telegram, Instagram or WhatsApp post, a quote card or
  screenshot, a link to one, or a few paragraphs of Arabic to translate, rather than a whole book
  or video.
---

# Translate an Arabic post

Run every command from the repo root (`cd "$(git -C "${CLAUDE_SKILL_DIR}" rev-parse --show-toplevel)"`;
other agents: the folder holding AGENTS.md), with `python` meaning `.venv/bin/python`. One post is
one run: `runs/<slug>/`, for example `runs/post-sabr-01`. First time here: `./install.sh`.

No chunks, no subagents: a post is small enough to do directly.

1. **Get the Arabic.** Pasted text: use it as given. A link: fetch the page with your web tools and
   take the post's text only. A screenshot or quote card: read the image and transcribe the Arabic
   exactly as printed.
2. **Start the run.** `python -m scripts.post init runs/<slug> --text "<arabic>"` (or `--from <file>`).
   It stores `source.txt` and prints the glossary subset to follow.
3. **Translate.** Follow `templates/post-translator.md` exactly and write `runs/<slug>/work/post.md`.
   Every quoted verse and hadith goes through the retrieval lookups.
4. **Check.** `python -m scripts.post check runs/<slug>` until it prints OK, then re-read the English
   against the Arabic line by line.
5. **Finish.** `python -m scripts.post finish runs/<slug> [--platform x|bluesky|threads|mastodon|instagram|linkedin|telegram|facebook] [--arabic]`
   writes `output/<slug>.txt`, or `.thread.txt` when a threading platform needs splitting, plus
   `output/review.md`. `--arabic` keeps the Arabic of quoted verses and hadith. New terms are merged
   into the master glossary; commit `data/glossary.json` and `data/glossary-changelog.md`.
6. **Deliver.** Show the user the finished text and anything flagged, especially a † hadith: that
   English is a translation of ours, not a published one, and the post says so.

Scheduling or publishing the post is a separate action: do it only when the user asks.

## Non-negotiables

- Never write a verse or hadith from memory. The lookups supply the wording; `scripts.post check`
  fails a verse whose English deviates, and anything else unverified is marked † automatically.
- A hadith you cannot find may be weak or fabricated. Say so to the user in plain words rather than
  quietly posting it: this tool checks wording against datasets, it does not grade hadith.
