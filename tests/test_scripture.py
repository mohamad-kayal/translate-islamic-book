from scripts.recheck_scripture import recheck_sentence
from subs.scripture import references, sentence_problem


class _Quran:
    def get_verse(self, s, a):
        return {(1, 1): {"saheeh": "sea river", "clear": "ocean stream"},
                (1, 2): {"saheeh": "mountain sun", "clear": "peak star"}}.get((s, a))


class _Hadith:
    def get(self, coll, num):
        return {"bukhari": {"english": "Narrated Umar: deeds depend on intentions."}}.get(coll)


def _s(en, kind="quran", ref="1:1", src="dataset", **kw):
    return dict({"segs": [0, 0], "type": kind, "en": en, "ref": ref, "src": src, "flags": []}, **kw)


def _problem(s):
    return sentence_problem(s, _Quran(), _Hadith())


def test_refs_parse_verse_ranges_and_lists():
    assert references("quran", "1:1-2", _Quran(), _Hadith()) == ["sea river mountain sun",
                                                                "ocean stream peak star"]
    assert len(references("hadith", "muslim 9, bukhari 1", _Quran(), _Hadith())) == 1


def test_refs_accept_semicolons_and_spelled_out_collections():
    assert len(references("hadith", "muslim 9; bukhari 1", _Quran(), _Hadith())) == 1
    index = type("I", (), {"get": lambda self, c, n: {"english": "e"} if c == "ibnmajah" else None})()
    assert references("hadith", "Ibn Majah 4164", _Quran(), index) == ["e"]


def test_verbatim_quote_passes_even_with_break_marks():
    assert _problem(_s("sea | river")) is None
    assert _problem(_s("deeds depend on | intentions", "hadith", "bukhari 1")) is None


def test_a_paraphrase_claiming_the_dataset_fails():
    assert "not the dataset's wording" in _problem(_s("the ocean and the lake"))


def test_lead_in_is_allowed_when_quote_names_the_verbatim_part():
    assert _problem(_s("He said: deeds depend on intentions", "hadith", "bukhari 1",
                       quote="deeds depend on intentions")) is None


def test_quote_must_actually_be_in_en():
    assert "not part of en" in _problem(_s("He said something else", "hadith", "bukhari 1",
                                           quote="deeds depend on intentions"))


def test_unknown_ref_fails():
    assert "not found" in _problem(_s("sea river", ref="200:1"))
    assert "not found" in _problem(_s("sea river", "hadith", "nowhere 1"))


def test_prose_and_fallbacks_are_not_checked():
    assert _problem(_s("anything", "prose", None, None)) is None
    assert _problem(_s("my own words", src="fallback")) is None


class _Long:
    def get(self, coll, num):
        return {"english": "one two three four five six seven eight"}


def test_recheck_records_the_quote_inside_commentary():
    s = _s("So he told them: | one two three four five six seven, | and that is the point",
           "hadith", "bukhari 1")
    assert recheck_sentence(s, _Quran(), _Long()) == "quote"
    assert s["quote"] == "one two three four five six seven" and s["src"] == "dataset"
    assert sentence_problem(s, _Quran(), _Long()) is None


def test_recheck_relabels_a_real_paraphrase():
    s = _s("In short, one two and then something else entirely", "hadith", "bukhari 1")
    assert recheck_sentence(s, _Quran(), _Long()) == "fallback"
    assert s["src"] == "fallback" and "not the dataset's wording" in s["flags"]
    assert sentence_problem(s, _Quran(), _Long()) is None


def test_recheck_relabels_an_unresolvable_ref():
    s = _s("That which is lawful is clear", "hadith", "bukhari & muslim")
    assert recheck_sentence(s, _Quran(), _Hadith()) == "fallback"


def test_recheck_leaves_good_sentences_alone():
    s = _s("one two three four five six", "hadith", "bukhari 1")
    before = dict(s)
    assert recheck_sentence(s, _Quran(), _Long()) is None and s == before
