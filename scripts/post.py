"""One social post or short passage: the smallest job this tool does.

    python -m scripts.post init   runs/<slug> (--from <file> | --text "<arabic>")
    python -m scripts.post check  runs/<slug>
    python -m scripts.post finish runs/<slug> [--platform x] [--arabic]

`init` stores the source and prints the glossary subset. The translator then writes
work/post.md using the same quran/hadith markers as a book (templates/post-translator.md),
so everything out.verify guarantees for a book holds for a post. `finish` checks it, harvests
new terms into the master, and writes output/<slug>.txt (or .thread.txt when a platform that
threads needs splitting) plus output/review.md.
"""
import argparse
import json
import pathlib
import re
import shutil
import sys

from out.assemble import mark_own_renderings
from out.lint import _chunk_findings
from out.verify import OWN_RENDERING_MARK, parse_markers, verify
from retrieval.glossary import harvest, load, mentioned
from retrieval.hadith_index import HadithIndex
from retrieval.normalize import normalize_arabic
from retrieval.quran_index import QuranIndex
from retrieval.verbatim import words

MASTER = "data/glossary.json"
CHANGELOG = "data/glossary-changelog.md"
# ponytail: plain character counts; X weighs URLs and emoji differently, so a post right at
# the limit may need a trim. Use the platform's real counter if that ever bites.
LIMITS = {"x": 280, "bluesky": 300, "threads": 500, "mastodon": 500, "instagram": 2200,
          "linkedin": 3000, "telegram": 4096, "facebook": 63206}
THREADED = {"x", "bluesky", "threads", "mastodon"}
_THREAD_SUFFIX_ROOM = 8   # " 12/34"
# A post shorter than this many English words per Arabic word likely lost a line.
_MIN_WORDS_PER_ARABIC_WORD = 0.7

_BLOCK = re.compile(r"<!--(quran|hadith)\s+[^>]*?-->\n(.*?)\n<!--/\1-->", re.S)
_LATIN = re.compile(r"[A-Za-z]")
_ARABIC_SPAN = re.compile(r"\[([^\]]*)\]\{[^}]*\}")
_EMPHASIS = re.compile(r"\*{1,2}([^*\n]+)\*{1,2}")
_HEADING = re.compile(r"^#{1,6}\s+", re.M)
_SENTENCE_END = re.compile(r"(?<=[.!?؟»”\"])\s+")


def _paths(run):
    run = pathlib.Path(run)
    return run, run / "source.txt", run / "work" / "post.md"


def init(run, text):
    run, source, _ = _paths(run)
    (run / "work").mkdir(parents=True, exist_ok=True)
    source.write_text(text.strip() + "\n", encoding="utf-8")
    return mentioned(text, load(MASTER))


def check(run, quran_index, hadith_index):
    """(problems, notes): the same deterministic bar a book's chapter has to clear."""
    run, source, post = _paths(run)
    if not post.exists():
        return ["no work/post.md yet"], []
    md = post.read_text(encoding="utf-8")
    report = verify(md, quran_index=quran_index, hadith_index=hadith_index)
    problems = list(report["problems"])
    lint_problems, warnings = _chunk_findings("post.md", md)
    problems += lint_problems
    problems += [w for w in warnings if "Arabic outside markers" in w]
    if "[[H" in md:
        problems.append("post.md: a [[H]] placeholder belongs to books, not posts")
    notes = ["quran %d, hadith %s" % (report["n_quran"], report.get("hadith_sources"))]
    notes += report["flagged"]
    arabic_words = len(normalize_arabic(source.read_text(encoding="utf-8")).split())
    english_words = len(words(re.sub(r"<!--.*?-->", " ", md, flags=re.S)))
    if english_words < _MIN_WORDS_PER_ARABIC_WORD * arabic_words:
        problems.append("post.md: only %d English words for %d Arabic words — did a line get "
                        "dropped?" % (english_words, arabic_words))
    return problems, notes


def _plain_block(m, with_arabic):
    lines = [ln.strip() for ln in m.group(2).split("\n") if ln.strip()]
    arabic = [ln for ln in lines if not _LATIN.search(ln)]
    english = " ".join(ln for ln in lines if _LATIN.search(ln))
    return "\n".join(arabic + [english]) if with_arabic else english


def to_plain_text(md, hadith_index, with_arabic=False):
    """The reader's text: markers gone, † on anything unverified, its note at the foot."""
    md, marked = mark_own_renderings(md, hadith_index)
    text = _BLOCK.sub(lambda m: _plain_block(m, with_arabic), md)
    text = _HEADING.sub("", _EMPHASIS.sub(r"\1", _ARABIC_SPAN.sub(r"\1", text)))
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if marked:
        text += "\n\n%s English is the translator's own rendering." % OWN_RENDERING_MARK
    return text


def split_thread(text, limit):
    """Greedy split at paragraphs, then sentences, then words; numbered 'n/N'."""
    room = limit - _THREAD_SUFFIX_ROOM
    pieces = []
    for paragraph in text.split("\n\n"):
        for i, sentence in enumerate(_SENTENCE_END.split(paragraph)):
            while len(sentence) > room:
                cut = sentence.rfind(" ", 0, room)
                cut = cut if cut > 0 else room
                pieces.append((i == 0, sentence[:cut].strip()))
                sentence, i = sentence[cut:].strip(), 1
            pieces.append((i == 0, sentence))
    parts = []
    for starts_paragraph, piece in pieces:
        glue = "\n\n" if starts_paragraph else " "
        if parts and len(parts[-1]) + len(glue) + len(piece) <= room:
            parts[-1] += glue + piece
        else:
            parts.append(piece)
    return ["%s %d/%d" % (p, i, len(parts)) for i, p in enumerate(parts, 1)]


def _review(run, md, notes, harvested):
    markers = parse_markers(md)
    lines = ["# Review — %s" % run.name, ""]
    for q in markers["quran"]:
        lines.append("- Qur'an %s:%s" % (q.get("s"), q.get("a")))
    for h in markers["hadith"]:
        lines.append("- hadith %s %s (%s)" % (h.get("coll"), h.get("cite") or h.get("num"),
                                              h.get("src")))
    lines += ["", "## Check"] + ["- %s" % n for n in notes]
    if harvested["added"] or harvested["conflicts"]:
        lines += ["", "## Glossary"]
        lines += ["- added: %s" % ar for ar in harvested["added"]]
        lines += ["- held, your call: %s (master has %r, this post used %r). Accept with "
                  "`python -m scripts.glossary resolve %s --accept %s`"
                  % (c["ar"], c["master"], c["proposed"], run, c["ar"])
                  for c in harvested["conflicts"]]
    return "\n".join(lines) + "\n"


def finish(run, platform=None, with_arabic=False):
    run, _, post = _paths(run)
    quran_index, hadith_index = QuranIndex.load(), HadithIndex.load()
    problems, notes = check(run, quran_index, hadith_index)
    if problems:
        return problems, None
    md = post.read_text(encoding="utf-8")
    text = to_plain_text(md, hadith_index, with_arabic)
    limit = LIMITS.get(platform)
    out_dir = run / "output"
    out_dir.mkdir(exist_ok=True)
    out = out_dir / ("%s.txt" % run.name)
    if limit and len(text) > limit:
        if platform not in THREADED:
            return ["%d characters is over %s's %d: shorten work/post.md"
                    % (len(text), platform, limit)], None
        out = out_dir / ("%s.thread.txt" % run.name)
        text = "\n\n---\n\n".join(split_thread(text, limit))
    out.write_text(text + "\n", encoding="utf-8")
    harvested = harvest(run, MASTER, CHANGELOG)
    (out_dir / "review.md").write_text(_review(run, md, notes, harvested), encoding="utf-8")
    return [], out


def main():
    ap = argparse.ArgumentParser(description="see module docstring")
    ap.add_argument("command", choices=["init", "check", "finish"])
    ap.add_argument("run")
    ap.add_argument("--from", dest="source", help="init: text file holding the post")
    ap.add_argument("--text", help="init: the post itself")
    ap.add_argument("--platform", choices=sorted(LIMITS),
                    help="finish: apply this platform's length limit")
    ap.add_argument("--arabic", action="store_true",
                    help="finish: keep the Arabic of quoted verses and hadith")
    args = ap.parse_args()

    if args.command == "init":
        if args.source and pathlib.Path(args.source).suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
            run = pathlib.Path(args.run)
            (run / "work").mkdir(parents=True, exist_ok=True)
            shutil.copyfile(args.source, run / ("source" + pathlib.Path(args.source).suffix.lower()))
            sys.exit("saved the image. Read it, write its Arabic exactly as printed, then run "
                     "init again with --text or --from a text file.")
        text = args.text or pathlib.Path(args.source).read_text(encoding="utf-8-sig")
        print(json.dumps(init(args.run, text), ensure_ascii=False, indent=2))
    elif args.command == "check":
        problems, notes = check(args.run, QuranIndex.load(), HadithIndex.load())
        for note in notes:
            print(note)
        for problem in problems:
            print("PROBLEM: %s" % problem)
        print("FAIL" if problems else "OK")
        sys.exit(1 if problems else 0)
    else:
        problems, out = finish(args.run, args.platform, args.arabic)
        for problem in problems:
            print("PROBLEM: %s" % problem)
        if problems:
            sys.exit(1)
        print("output: %s" % out)


if __name__ == "__main__":
    main()
