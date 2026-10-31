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
