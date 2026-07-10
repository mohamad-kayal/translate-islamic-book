from retrieval.quran_index import QuranIndex

# Synthetic 3-ayah surah (tashkeel-free base letters).
ARABIC = {(1, 1): "بحر نهر", (1, 2): "جبل شمس قمر", (1, 3): "ليل نهار"}
SAHEEH = {(1, 1): "sea river", (1, 2): "mountain sun moon", (1, 3): "night day"}
CLEAR = {(1, 1): "the sea", (1, 2): "a mountain", (1, 3): "the night"}


def idx():
    return QuranIndex(ARABIC, SAHEEH, CLEAR)


def test_single_ayah_with_tashkeel_query():
    # query carries harakat and must still match the bare ayah 1
    assert idx().identify_span("بَحر نَهر") == (1, 1, 1, 1.0)


def test_multi_ayah_range():
    assert idx().identify_span("جبل شمس قمر ليل نهار")[:3] == (1, 2, 3)


def test_partial_trailing_ayah():
    assert idx().identify_span("جبل شمس")[:3] == (1, 2, 2)


def test_midayah_quotation_resolves_to_containing_ayah():
    # 'قمر' is the LAST word of ayah 2 -> a partial/mid-ayah quote still resolves to ayah 2
    assert idx().identify_span("قمر")[:3] == (1, 2, 2)


def test_absent_text_returns_none():
    assert idx().identify_span("زيتون تين") is None


def test_alef_orthography_insensitive():
    # ayah stored with full alef (كتاب); a query missing that alef (Uthmani-style) still matches
    i2 = QuranIndex({(1, 1): "كتاب مبين"}, {(1, 1): "x"}, {(1, 1): "y"})
    assert i2.identify_span("كتب مبين")[:3] == (1, 1, 1)


def test_get_verse():
    assert idx().get_verse(1, 2)["saheeh"] == "mountain sun moon"
    assert idx().get_verse(9, 9) is None


def test_no_midword_substring_match():
    # 'بل شم' appears inside 'جبل شمس' but is not a word-boundary quote -> no match
    assert idx().identify_span("بل شم") is None


def test_short_word_does_not_match_inside_longer_word():
    # a query that is a substring of a longer word must not match it
    i2 = QuranIndex({(1, 1): "مطهرة نهر", (2, 1): "طه"}, {(1, 1): "x", (2, 1): "y"},
                    {(1, 1): "x", (2, 1): "y"})
    assert i2.identify_span("طه")[:3] == (2, 1, 1)


# A mutashabih phrase: identical wording at three locations (twice in surah 2,
# once in surah 1 — like ولقد يسرنا القرآن للذكر at 54:17/22/32/40).
REPEATED = {(1, 1): "بحر نهر", (1, 2): "جبل شمس قمر",
            (2, 1): "بحر نهر", (2, 5): "نجم بحر نهر ضوء", (2, 7): "سحاب مطر"}


def ridx():
    eng = {k: "x" for k in REPEATED}
    return QuranIndex(REPEATED, eng, dict(eng))


def test_identify_spans_lists_every_location():
    spans, total = ridx().identify_spans("بحر نهر")
    assert total == 3
    assert spans == [(1, 1, 1), (2, 1, 1), (2, 5, 5)]


def test_identify_spans_cap_keeps_true_total():
    spans, total = ridx().identify_spans("بحر نهر", cap=2)
    assert len(spans) == 2 and total == 3


def test_identify_span_unchanged_returns_first_location():
    assert ridx().identify_span("بحر نهر") == (1, 1, 1, 1.0)


def test_identify_spans_unique_phrase():
    spans, total = ridx().identify_spans("سحاب مطر")
    assert total == 1 and spans == [(2, 7, 7)]


def test_nearest_suggests_closest_ayah_on_miss():
    # 3 of 4 query words sit in ayah (1,2): no exact span, but a strong suggestion
    i = idx()
    assert i.identify_span("جبل شمس قمر خطأ") is None
    near = i.nearest("جبل شمس قمر خطأ")
    assert near and near[0][0] == 1 and near[0][1] == 2 and near[0][2] >= 0.7


def test_nearest_empty_when_nothing_shared():
    assert idx().nearest("زيتون تين") == []
