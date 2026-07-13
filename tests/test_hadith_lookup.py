from retrieval.hadith_index import HadithIndex

# Synthetic records; queries are word-subsets of a record so containment is decisive.
RECORDS = [
    {"collection": "bukhari", "number": 1,
     "arabic": "انما الاعمال بالنيات وانما لكل امرئ ما نوى",
     "english": "Actions are but by intention...", "reference": {"book": 1, "hadith": 1}},
    {"collection": "muslim", "number": 2408,
     "arabic": "كتاب الله هو حبل الله من اتبعه كان على الهدى ومن تركه كان على ضلالة",
     "english": "The Book of Allah is the rope of Allah...", "reference": {"book": 44, "hadith": 55}},
    {"collection": "bukhari", "number": 79,
     "arabic": "مثل ما بعثني الله به من الهدى والعلم كمثل الغيث الكثير اصاب ارضا",
     "english": "The example of guidance and knowledge...", "reference": {"book": 3, "hadith": 20}},
]


def idx():
    return HadithIndex.from_records(RECORDS)


def test_matches_full_matn():
    r = idx().match("انما الاعمال بالنيات وانما لكل امرئ ما نوى")
    assert r["collection"] == "bukhari" and r["number"] == 1 and r["confidence"] >= 0.9


def test_matches_by_content_not_number():
    r = idx().match("كتاب الله هو حبل الله من اتبعه كان على الهدى")
    assert r["collection"] == "muslim" and "rope" in r["english"]


def test_below_threshold_returns_none():
    assert idx().match("زيتون تين رمان عنب موز برتقال فراولة") is None


def test_empty_query_returns_none():
    assert idx().match("") is None


# The same matn in several collections: a derivative "forty" collection stores it
# matn-only; the canonical collection carries an isnad prefix (longer entry, lower recall).
MATN = "لا يؤمن احدكم حتى يحب لاخيه ما يحب لنفسه"
MULTI = [
    {"collection": "dehlawi", "number": 7, "arabic": MATN,
     "english": "None of you believes (dehlawi)...", "reference": {}},
    {"collection": "nawawi", "number": 13, "arabic": MATN,
     "english": "None of you believes (nawawi)...", "reference": {}},
    {"collection": "bukhari", "number": 13, "arabic": "حدثنا مسدد قال " + MATN,
     "english": "None of you believes (bukhari)...", "reference": {}},
]


def midx():
    return HadithIndex.from_records(MULTI)


def test_canonical_collection_wins_ties():
    """Identical containment across collections must not favor the short matn-only
    entry (the pre-fix behavior: recall ranked the forty-collections above bukhari)."""
    r = midx().match(MATN)
    assert r["collection"] == "bukhari" and r["number"] == 13


def test_prefer_overrides_canonical():
    r = midx().match(MATN, prefer="nawawi")
    assert r["collection"] == "nawawi" and r["number"] == 13


def test_prefer_outside_eps_does_not_override():
    """prefer is a tie-break within EPS, not a quality override: when the preferred
    collection's entry misses query words, the honest (verbatim) match still wins."""
    records = MULTI + [
        {"collection": "muslim", "number": 45,
         "arabic": "لا يؤمن احدكم حتى يحب الخير كله",   # different ending
         "english": "variant", "reference": {}},
    ]
    r = HadithIndex.from_records(records).match(MATN, prefer="muslim")
    assert r["collection"] == "bukhari"


def test_alternates_list_other_shortlist_collections_in_canonical_order():
    r = midx().match(MATN)
    assert [a["collection"] for a in r["alternates"]] == ["nawawi", "dehlawi"]
    assert all(a["confidence"] >= 0.9 for a in r["alternates"])
    assert all(set(a) == {"collection", "number", "confidence"} for a in r["alternates"])


def test_alternates_empty_for_unique_match():
    r = idx().match("انما الاعمال بالنيات وانما لكل امرئ ما نوى")
    assert r["alternates"] == []


def test_unknown_prefer_collection_is_harmless():
    r = midx().match(MATN, prefer="ahmad")   # not bundled: no-op, canonical order holds
    assert r["collection"] == "bukhari"
