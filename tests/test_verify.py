from out.verify import parse_markers, verify
from retrieval.hadith_index import HadithIndex
from retrieval.quran_index import QuranIndex

GOOD = (
    "intro\n"
    "<!--quran s=4 a=59-59 tr=saheeh-->\n(...) [An-Nisa: 59]\n<!--/quran-->\n"
    "<!--hadith coll=bukhari num=79 conf=1.0 src=dataset-->\n[[H]] ... <!--/hadith-->\n"
)

# Tiny synthetic datasets for body verification.
QIDX = QuranIndex({(1, 1): "بحر نهر", (1, 2): "جبل شمس قمر"},
                  {(1, 1): "sea river", (1, 2): "mountain sun moon"},
                  {(1, 1): "x", (1, 2): "y"})
HIDX = HadithIndex.from_records([
    {"collection": "bukhari", "number": 79,
     "arabic": "مثل ما بعثني الله به من الهدى", "english": "The parable...", "reference": {}},
])


def _q(body, s=1, a="1-1", tr="saheeh"):
    return "<!--quran s=%d a=%s tr=%s-->\n%s\n<!--/quran-->\n" % (s, a, tr, body)


def test_body_check_verbatim_ok():
    md = _q('(بَحر نَهر) [X: 1]\n"sea river" [X: 1]')
    assert verify(md, quran_index=QIDX)["problems"] == []


def test_body_check_catches_deviation():
    # one word replaced -> retyped/hallucinated verse must be caught
    md = _q('(بَحر قمر) [X: 1]\n"sea river" [X: 1]')
    probs = verify(md, quran_index=QIDX)["problems"]
    assert any("deviates" in p for p in probs)


def test_body_check_accepts_partial_quote():
    # author quoted only part of ayah 2 -> substring of the dataset text is fine
    md = _q('(جبل شمس) [X: 2]', a="2-2")
    assert verify(md, quran_index=QIDX)["problems"] == []


def test_body_check_accepts_single_word_partial_quote():
    # author re-quotes ONE word (e.g. عصاي in Taha 18) while commenting -> still verbatim
    md = _q('(شمس) [X: 2]', a="2-2")
    assert verify(md, quran_index=QIDX)["problems"] == []


def test_body_check_still_catches_word_not_in_verse():
    md = _q('(زيتون) [X: 2]', a="2-2")   # زيتون is not in ayah 2 (جبل شمس قمر)
    assert any("deviates" in p for p in verify(md, quran_index=QIDX)["problems"])


def test_body_check_multiverse_with_numbers_and_ref():
    md = _q('(بحر نهر (١) جبل شمس قمر (٢)) [X: 1-2]\n"sea river mountain sun moon"', a="1-2")
    assert verify(md, quran_index=QIDX)["problems"] == []


# Hadith entries carry the isnad, spell out honorifics, and have orthographic /
# transmission variants — so matn verification is honorific- and alef-insensitive.
HIDX_REAL = HadithIndex.from_records([
    {"collection": "muslim", "number": "6228",
     # full entry: isnad prefix + spelled-out honorific "عز وجل" (book uses ﷻ)
     "arabic": "حدثنا محمد بن بكار حدثنا حسان قال كتاب الله عز وجل هو حبل الله "
               "من اتبعه كان على الهدى ومن تركه كان على ضلالة",
     "english": "x", "reference": {}},
    {"collection": "abudawud", "number": "4605",
     # dataset transmission says "لا ندري"; a book may quote "لا أدري"
     "arabic": "حدثنا احمد قال لا الفين احدكم متكئا على اريكته فيقول لا ندري "
               "ما وجدنا في كتاب الله اتبعناه",
     "english": "x", "reference": {}},
])


def test_hadith_body_check():
    good = ('<!--hadith coll=bukhari num=79 conf=1.0 src=dataset-->\n'
            '«مثل ما بعثني الله به من الهدى»\n"The parable..." (Bukhari 79)\n<!--/hadith-->')
    assert verify(good, hadith_index=HIDX)["problems"] == []
    wrong_num = good.replace("num=79", "num=80")
    assert any("not found" in p for p in verify(wrong_num, hadith_index=HIDX)["problems"])


def test_hadith_matn_verbatim_despite_isnad_and_honorific():
    # book pastes matn only, with ﷻ ligature; dataset has isnad + "عز وجل" -> still clean
    md = ('<!--hadith coll=muslim num=6228 conf=1.0 src=dataset-->\n'
          '«كِتَابُ اللَّهِ ﷻ هُوَ حَبْلُ اللَّهِ، مَنِ اتَّبَعَهُ كَانَ عَلَى الْهُدَى»\n'
          '"..." (Muslim 2408)\n<!--/hadith-->')
    r = verify(md, hadith_index=HIDX_REAL)
    assert r["problems"] == [] and r["flagged"] == []


def test_hadith_transmission_variant_is_flagged_not_a_problem():
    # book "لا أدري" vs dataset "لا ندري" — one authentic-variant word -> flag for review
    md = ('<!--hadith coll=abudawud num=4605 conf=1.0 src=dataset-->\n'
          '«لَا أُلْفِيَنَّ أَحَدَكُمْ مُتَّكِئًا عَلَى أَرِيكَتِهِ فَيَقُولُ لَا أَدْرِي مَا وَجَدْنَا فِي كِتَابِ اللَّهِ اتَّبَعْنَاهُ»\n'
          '"..." (Abu Dawud 4605)\n<!--/hadith-->')
    r = verify(md, hadith_index=HIDX_REAL)
    assert r["problems"] == []
    assert any("abudawud 4605" in f for f in r["flagged"])


def test_hadith_wrong_hadith_is_a_problem():
    # a totally different matn under this number -> mostly-absent words -> hard problem
    md = ('<!--hadith coll=muslim num=6228 conf=1.0 src=dataset-->\n'
          '«إِنَّمَا الْأَعْمَالُ بِالنِّيَّاتِ وَإِنَّمَا لِكُلِّ امْرِئٍ مَا نَوَى»\n'
          '"..." (Muslim 6228)\n<!--/hadith-->')
    assert any("deviates" in p for p in verify(md, hadith_index=HIDX_REAL)["problems"])


def test_quran_fallback_is_flagged_not_problem():
    md = "<!--quran s=0 a=0-0 tr=fallback-->\n(something) [X]\n<!--/quran-->"
    r = verify(md, quran_index=QIDX)
    assert r["problems"] == []
    assert any("fallback" in f.lower() for f in r["flagged"])


def test_unbalanced_markers_reported():
    md = "<!--quran s=1 a=1-1 tr=saheeh-->\n(بحر نهر)\n"  # no closer
    r = verify(md)
    assert any("unbalanced" in p.lower() or "unclosed" in p.lower() for p in r["problems"])


def test_parse_counts():
    m = parse_markers(GOOD)
    assert len(m["quran"]) == 1 and len(m["hadith"]) == 1
    assert m["quran"][0]["s"] == "4" and m["hadith"][0]["coll"] == "bukhari"


def test_clean_report_has_no_problems():
    r = verify(GOOD)
    assert r["n_quran"] == 1 and r["n_hadith"] == 1
    assert r["problems"] == [] and r["flagged"] == []


def test_flags_low_confidence_and_fallback():
    md = "<!--hadith coll=ahmad num=23482 conf=0.4 src=fallback-->x<!--/hadith-->"
    r = verify(md)
    assert any("review" in f.lower() or "fallback" in f.lower() or "confidence" in f.lower()
               for f in r["flagged"])


def test_problems_on_bad_surah():
    md = "<!--quran s=200 a=1-1 tr=saheeh-->x<!--/quran-->"
    r = verify(md)
    assert any("surah" in p.lower() for p in r["problems"])


def test_fallback_placeholder_collection_is_flagged_not_problem():
    # a hadith not in the dataset (e.g. al-Darimi, which isn't bundled) is a fallback;
    # its collection may be a placeholder or an unbundled name — that is review, not error
    md = "<!--hadith coll=0 num=0 conf=0 src=fallback-->\nx\n<!--/hadith-->"
    r = verify(md)
    assert r["problems"] == []
    assert any("fallback" in f for f in r["flagged"])


def test_dataset_hadith_unknown_collection_is_a_problem():
    md = "<!--hadith coll=bogus num=1 conf=1.0 src=dataset-->\nx\n<!--/hadith-->"
    assert any("unknown hadith collection" in p for p in verify(md)["problems"])


def test_replacement_character_in_hadith_body_is_flagged():
    # 76 dataset entries carry U+FFFD (OCR damage, e.g. "brot�ier"); pasted
    # verbatim into a book it must reach review.md, not ship silently
    md = ('<!--hadith coll=bukhari num=6011 conf=1.0 src=dataset-->\n'
          '«...»\n"your brot�ier" (al-Bukhari 6011)\n<!--/hadith-->')
    assert any("U+FFFD" in f for f in verify(md)["flagged"])


def test_replacement_character_in_quran_body_is_flagged():
    md = '<!--quran s=1 a=1-1 tr=saheeh-->\n(بحر نهر) [X: 1]\n"sea �river" [X: 1]\n<!--/quran-->'
    assert any("U+FFFD" in f for f in verify(md)["flagged"])


def test_clean_bodies_not_flagged_for_ufffd():
    assert not any("U+FFFD" in f for f in verify(GOOD)["flagged"])
