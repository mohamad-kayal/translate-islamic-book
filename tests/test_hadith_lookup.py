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
