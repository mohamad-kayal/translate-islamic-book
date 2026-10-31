"""Merge translated chunk markdowns into one book: title, hadith numbers, cleanup."""
import argparse
import glob
import os
import re

from retrieval.normalize import normalize_arabic

# Chunk-seam working notes ('*[Ornamental divider]*', '*[Blank page]*',
# '*[Ornamental page: Basmala]*') are for the orchestrator, not the reader.
_PAGE_NOTE = re.compile(r"^\*\[[^\]]*\]\*\s*$", re.M)
_EXTRA_BLANKS = re.compile(r"\n{3,}")
_QURAN_FULL = re.compile(r"(<!--quran\s+([^>]*?)-->\n)(.*?)(\n<!--/quran-->)", re.S)
_REF_TAIL = re.compile(r"\s*(\[[^\]]*\])\s*$")
_RUB_MARK = "۞"   # U+06DE start of rub-el-hizb — a division marker, not verse text
_TO_ARABIC = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")

# Index patterns
_H2 = re.compile(r"^##\s+(?!Index of|Glossary)(.+?)\s*$", re.M)
_QURAN_MARK = re.compile(r"<!--quran\s+s=(\d+)\s+a=(\d+)-(\d+)[^>]*-->")
_HADITH_MARK = re.compile(r"<!--hadith\s+coll=(\w+)\s+num=(\S+)[^>]*-->")

_COLL_NAMES = {
    "bukhari": "al-Bukhari", "muslim": "Muslim", "abudawud": "Abu Dawud",
    "tirmidhi": "al-Tirmidhi", "nasai": "al-Nasa'i", "ibnmajah": "Ibn Majah",
    "malik": "Malik", "ahmad": "Ahmad", "darimi": "al-Darimi",
    "hakim": "al-Hakim", "bayhaqi": "al-Bayhaqi",
}


def _arabic_num(n):
    return str(n).translate(_TO_ARABIC)


def _ar(s):
    return "[%s]{lang=ar dir=rtl}" % s


def front_matter(meta):
    cover = ('::: {.cover}\n'
             '%s\n\n# %s\n\n%s\n\n%s\n:::\n\n'
             % (_ar(meta["title_ar"]), meta["title_en"],
                _ar(meta["author_ar"]), meta["author_en"]))
    half = '::: {.half-title}\n%s\n:::\n\n' % meta["title_en"]
    lines = ["::: {.copyright}", "**%s**  " % meta["title_en"],
             "%s  " % meta["author_en"]]
    if meta.get("translator"):
        lines.append("Translated by %s  " % meta["translator"])
    if meta.get("edition"):
        lines.append("%s  " % meta["edition"])
    if meta.get("year"):
        lines.append("%s  " % meta["year"])
    lines += ["",
              "Qur'anic quotations are the Saheeh International translation; "
              "hadith are given in their published translations. All sacred "
              "text is retrieved verbatim from source datasets and "
              "machine-verified, never machine-written.", "",
              "This edition has not been fully verified against the Arabic "
              "source by a human and may contain errors.", ":::", ""]
    return cover + half + "\n".join(lines) + "\n"


def back_matter():
    return ("\n\n::: {.colophon}\n"
            "Set in Cardo and Amiri. Composed with the translate-islamic-book "
            "pipeline.\n:::\n")


def _renumber(m, quran_index):
    head, attrs_raw, body, tail = m.group(1), m.group(2), m.group(3), m.group(4)
    attrs = dict(re.findall(r"(\w+)=(\S+)", attrs_raw))
    if attrs.get("s", "0") == "0" or attrs.get("tr") == "fallback":
        return m.group(0)
    try:
        s = int(attrs["s"])
        a0, a1 = (int(x) for x in attrs["a"].split("-"))
    except (KeyError, ValueError):
        return m.group(0)
    lines = body.split("\n")
    idx = next((i for i, ln in enumerate(lines) if ln.strip()), None)
    if idx is None:
        return m.group(0)
    ar_line = lines[idx]
    ref_m = _REF_TAIL.search(ar_line)
    ref = ref_m.group(1) if ref_m else ""
    arabic = (ar_line[:ref_m.start()] if ref_m else ar_line).replace(_RUB_MARK, "")
    arabic = re.sub(r"\s+", " ", arabic).strip()
    verses = [quran_index.get_verse(s, a) for a in range(a0, a1 + 1)]
    if any(v is None for v in verses):
        return m.group(0)
    full = " ".join(v["arabic"] for v in verses)
    if a1 > a0 and normalize_arabic(arabic) == normalize_arabic(full):
        # canonical, dataset-sourced, one ayah number after each ayah
        arabic = " ".join("%s (%s)" % (v["arabic"], _arabic_num(a))
                          for a, v in zip(range(a0, a1 + 1), verses))
    # strip rub-el-hizb marks last — they occur in the dataset text itself (e.g. 28:12)
    arabic = re.sub(r"\s+", " ", arabic.replace(_RUB_MARK, "")).strip()
    lines[idx] = arabic + ((" " + ref) if ref else "")
    return head + "\n".join(lines) + tail


_CHAP_PREFIX = re.compile(
    r"^((?:Chapter|Part|Book|Section|Baab|Bab)\s+[\dIVXLCivxlc]+(?:\.\d+)*)\b")


def _short_chapter(title):
    """Index locators stay scannable: a long 'Chapter 26: The Centrality of…' collapses
    to 'Chapter 26'. Titles without that pattern (already short) are returned whole."""
    m = _CHAP_PREFIX.match(title)
    return m.group(1) if m else title


def _chapter_at(md, pos):
    """The nearest '## ' chapter heading at or before pos (else 'Front matter'),
    shortened to a scannable locator for the index."""
    best = "Front matter"
    for m in _H2.finditer(md):
        if m.start() <= pos:
            best = m.group(1)
        else:
            break
    return _short_chapter(best)


def build_indexes(book_md):
    verses, hadith = [], []
    for m in _QURAN_MARK.finditer(book_md):
        s, a0, a1 = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if s == 0:
            continue  # fallback marker, not a locatable citation
        verses.append((s, a0, a1, _chapter_at(book_md, m.start())))
    for m in _HADITH_MARK.finditer(book_md):
        coll, num = m.group(1), m.group(2)
        if coll == "0":
            continue  # fallback marker, not a locatable citation
        hadith.append((coll, num, _chapter_at(book_md, m.start())))
    if not verses and not hadith:
        return ""

    def _section(heading, entries):
        # entries wrapped in a .index fenced div, one paragraph each, so convert
        # can set them ragged (and columned) instead of as justified body prose.
        return "## %s\n\n::: {.index}\n%s\n:::\n" % (heading, "\n\n".join(entries))

    sections = []
    if verses:
        seen, entries = set(), []
        for s, a0, a1, chap in sorted(verses, key=lambda v: (v[0], v[1], v[2])):
            ref = "Surah %d:%d" % (s, a0) + ("" if a0 == a1 else "–%d" % a1)
            key = (ref, chap)
            if key in seen:
                continue
            seen.add(key)
            entries.append("%s — *%s*" % (ref, chap))
        sections.append(_section("Index of Qur'anic Verses", entries))
    if hadith:
        seen, entries = set(), []

        def _sortkey(h):
            try:
                return (h[0], int(h[1]))
            except ValueError:
                return (h[0], 1 << 30)
        for coll, num, chap in sorted(hadith, key=_sortkey):
            ref = "%s %s" % (_COLL_NAMES.get(coll, coll.title()), num)
            key = (ref, chap)
            if key in seen:
                continue
            seen.add(key)
            entries.append("%s — *%s*" % (ref, chap))
        sections.append(_section("Index of Hadith", entries))
    return "\n\n".join(sections)


def number_quran_ayat(md, quran_index):
    """Insert ayah numbers (Arabic-Indic) after each ayah in every FULL multi-ayah
    Quran block, sourced from the dataset, and strip rub-el-hizb division marks.
    Partial quotes and single ayat keep their text (marks stripped, no numbers)."""
    return _QURAN_FULL.sub(lambda m: _renumber(m, quran_index), md)


def assign_hadith_numbers(md, number=True):
    """With number=True, replace [[H]] with '**1.**', '**2.**'… (main) and [[HA]]
    with '**1-A.**'… (appendix) — for books that present hadith as a numbered
    collection. With number=False, strip the markers cleanly (both line-initial
    '[[H]] On the authority…' and mid-sentence '…the hadith [[H]]:') — for books
    that cite hadith inline as evidence, which is the common case."""
    if not number:
        md = re.sub(r"\[\[HA?\]\][ \t]*", "", md)   # marker + following inline space
        md = re.sub(r"[ \t]{2,}", " ", md)
        md = re.sub(r"[ \t]+([:.,;])", r"\1", md)    # tidy '…hadith :' -> '…hadith:'
        return md
    main = {"n": 0}
    app = {"n": 0}

    def _main(_):
        main["n"] += 1
        return "**%d.**" % main["n"]

    def _app(_):
        app["n"] += 1
        return "**%d-A.**" % app["n"]

    md = re.sub(r"\[\[HA\]\]", _app, md)
    md = re.sub(r"\[\[H\]\]", _main, md)
    return md


def strip_page_notes(md):
    md = _PAGE_NOTE.sub("", md)
    return _EXTRA_BLANKS.sub("\n\n", md)


def append_glossary(book_md, glossary):
    """Append a '## Glossary' section built from glossary['terms'] only, sorted by translit."""
    terms = (glossary or {}).get("terms") or {}
    if not terms:
        return book_md
    rows = sorted(terms.items(), key=lambda kv: kv[1]["translit"].casefold())
    entries = "\n\n".join(
        "*%s* · [%s]{lang=ar dir=rtl} · %s" % (v["translit"], ar, v["english"])
        for ar, v in rows)
    return "%s\n\n## Glossary\n\n::: {.glossary}\n%s\n:::\n" % (book_md, entries)


def merge(chunk_texts):
    return "\n\n".join(t.strip("\n") for t in chunk_texts)


def assemble(chunk_dir, out_path, title=None, author=None, quran_index=None,
             hadith_numbers=True, glossary=None, indexes=False, matter=False, meta=None):
    files = sorted(glob.glob(os.path.join(chunk_dir, "chunk_*.md")))
    body = merge([open(f, encoding="utf-8").read() for f in files])
    body = strip_page_notes(body)
    if quran_index is not None:
        body = number_quran_ayat(body, quran_index)
    book = assign_hadith_numbers(body, number=hadith_numbers)
    if matter and meta:
        book = "%s%s" % (front_matter(meta), book)
    if title and not (matter and meta):
        # pandoc title block: becomes the HTML title page (before the ToC) and
        # the Title-styled opening paragraph in DOCX. Skipped when front matter is
        # on — the cover div is the title page, and it must be page one (the pandoc
        # block would otherwise render above the cover).
        head = "%% %s\n" % title
        if author:
            head += "%% %s\n" % author
        book = "%s\n%s" % (head, book)
    if glossary:
        book = append_glossary(book, glossary)
    if indexes:
        idx_text = build_indexes(book)
        if idx_text:
            book = "%s\n\n%s" % (book, idx_text)
    if matter and meta:
        book = "%s%s" % (book, back_matter())
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(book)
    return book


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Assemble translated chunks into one book markdown.")
    p.add_argument("chunk_dir")
    p.add_argument("out_path")
    p.add_argument("--title", help="book title in English (title page + document title)")
    p.add_argument("--title-ar", dest="title_ar", help="book title in Arabic (front matter)")
    p.add_argument("--author", help="author line in English under the title")
    p.add_argument("--author-ar", dest="author_ar", help="author name in Arabic (front matter)")
    p.add_argument("--no-numbering", action="store_true",
                   help="skip dataset-sourced ayah numbering")
    p.add_argument("--no-hadith-numbers", action="store_true",
                   help="strip hadith markers instead of numbering them "
                        "(for books that cite hadith inline, not as a numbered collection)")
    p.add_argument("--glossary", help="path to the book's glossary.json (adds a Glossary appendix)")
    p.add_argument("--indexes", action="store_true",
                   help="build citation indexes (Qur'anic Verses and Hadith)")
    p.add_argument("--matter", action="store_true",
                   help="add front/back matter (cover, half-title, copyright, colophon)")
    p.add_argument("--translator", help="translator name (optional, for front matter)")
    p.add_argument("--edition", help="edition line (optional, for front matter)")
    p.add_argument("--year", help="publication year (optional, for front matter)")
    args = p.parse_args()
    gloss = None
    if args.glossary:
        from retrieval.glossary import load as _load_gloss
        gloss = _load_gloss(args.glossary)
    meta = None
    if args.matter:
        # start from the glossary 'book' block (if any), then overlay CLI args (CLI wins)
        meta = dict(gloss.get("book", {})) if gloss else {}
        for key, val in (("title_en", args.title), ("title_ar", args.title_ar),
                         ("author_en", args.author), ("author_ar", args.author_ar),
                         ("translator", args.translator), ("edition", args.edition),
                         ("year", args.year)):
            if val:
                meta[key] = val
        missing = [k for k in ("title_en", "title_ar", "author_en", "author_ar")
                   if not meta.get(k)]
        if missing:
            p.error("--matter needs title_en, title_ar, author_en, author_ar — supply a "
                    "--glossary with a book block or pass "
                    "--title/--title-ar/--author/--author-ar; missing: %s" % ", ".join(missing))
    qi = None
    if not args.no_numbering:
        from retrieval.quran_index import QuranIndex
        qi = QuranIndex.load()
    assemble(args.chunk_dir, args.out_path, title=args.title, author=args.author,
             quran_index=qi, hadith_numbers=not args.no_hadith_numbers, glossary=gloss,
             indexes=args.indexes, matter=args.matter, meta=meta)
    print("assembled -> %s" % args.out_path)
