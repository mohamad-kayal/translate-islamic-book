# PRODUCT.md — SRT Review Editor

## Register
**Product.** A focused tool; design serves the reviewing task and disappears into it.

## Users & Purpose
A single reviser (the pipeline's operator — Arabic-literate, technical) checking and correcting
the English subtitles the `translate-srt` skill produces, usually **on a phone**, often alongside
the source video, in short meticulous sessions. The job on every screen: read a cue, judge it
(is it faithful? does it read in time?), fix text or timing, move on. Fully client-side, no login,
files never leave the device (Firebase Hosting, single `index.html`).

## Primary tasks
1. Open an `.srt`/`.vtt`, scroll a long cue list smoothly (1000–2500 cues per lecture).
2. Tap a cue to edit its text; see reading-speed (CPS) and line-length (CPL) feedback live.
3. Nudge or type timings; catch overlaps.
4. Search / find-replace; jump to a cue or timecode.
5. Consult the shared glossary; see agreed terms highlighted in the text.
6. Review Arabic ↔ English side by side (from the run's `bilingual.md`).
7. Export a clean, re-indexed `.srt`.

## Design direction — "a proofing desk"
Not a consumer app; a quiet workspace for text work. **Dark-first**, light toggle. The **text is
the hero**. A **warm/cool language split**: cool-neutral surfaces for English/UI, a subtly warm
"manuscript" surface + system Arabic serif for the Arabic reference — the split encodes
language + direction, not decoration. **Color strategy: Restrained.** One accent (blue-violet)
for selection/primary only. The **one place color carries meaning** is the CPS/CPL severity band
(green → amber → red); the accent is kept off that band so "selected" never reads as "too fast."
Monospace timecodes (data). System font stacks (self-contained, offline, no external fetches).

## Anti-references (what it must NOT feel like)
- A SaaS dashboard (no hero-metric tiles, no eyebrow kickers, no gradient accents).
- A flashy consumer captions app (no rounded-everything, no playful motion).
- A generic dark IDE clone (the warm Arabic surface + restraint are the differentiators).

## Accessibility
Body text ≥4.5:1 both themes. Touch targets ≥44px. Full keyboard path (edit, nav, save).
`prefers-reduced-motion` honored. RTL correctness for Arabic (dir + bidi isolation).
