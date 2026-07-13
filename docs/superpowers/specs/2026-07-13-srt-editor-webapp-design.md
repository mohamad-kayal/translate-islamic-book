# Mobile SRT Editor Web App — Design (sub-project 2)

**Date:** 2026-07-13 · **Status:** planned; build starts after the translation skill ships.
Visual direction to be committed at build time (impeccable skill), per house rules.

## Goal

A mobile-first, fully client-side SRT editor for the human revision pass over the pipeline's
English subtitles — single-file `editor/index.html` (vanilla HTML/CSS/JS, no framework, no
build step), deployed to Firebase Hosting, usable with no login. Files never leave the device.

## Core (MVP)

- **Load:** file picker + drag-and-drop; tolerant SRT parse (same rules as `subs/srt_io.py`,
  hand-rolled ~40-line JS); UTF-8 BOM handling.
- **Cue list:** card per cue (index, in/out times, text), **virtual scrolling** (2,000+ cues
  must scroll smoothly on a phone — render visible window + buffer, DOM recycling).
- **Edit:** tap a card → inline textarea (bottom-sheet on small screens); touch targets ≥44 px.
  Auto `dir="rtl"` when the text is Arabic-dominant.
- **Timing:** tap a timestamp → ±100 ms nudge buttons + direct entry; validate end>start and
  no overlap with neighbors.
- **Live badges:** per-cue CPS + CPL, red past 20 CPS / 42 chars/line.
- **Autosave:** every edit → IndexedDB keyed by filename+size hash; "restore session" on reopen.
- **Undo/redo**, **search + find/replace**, **jump to cue #/timecode**.
- **Export:** re-indexed clean `.srt` via Blob download (VTT later if ever needed).

## Pipeline integration (the differentiator)

- **Bilingual review mode:** open the run's `bilingual.md` (or a JSON sidecar if we add one)
  alongside the `.srt` — stacked Arabic/English per sentence for fidelity checking.
- **Glossary panel:** load this repo's `data/glossary.json` (copied into the deploy, or fetched
  from the GitHub raw URL once the repo has a remote); collapsible reference panel; highlight
  glossary terms inside cue text with translit/English tooltip.
- **Flag for review:** per-cue flag exported as a notes text block (mirrors review.md culture).

## Non-goals

No backend, no auth, no Firestore (revisit only if multi-device sessions are ever wanted —
Spark tier suffices regardless). No video preview in MVP (a later nice-to-have; audio-sync
scrubbing is desktop-tool territory).

## Deploy

`firebase init hosting` + `firebase deploy` from `editor/`. Free Spark tier. Confirm with the
user before first public deploy (house rule: outward-facing publish is opt-in).
