from retrieval.verbatim import OWN, STITCHED, VERBATIM, english_status, words

DATASET = ("Narrated Umar: I heard Allah's Messenger (ﷺ) saying, \"The reward of deeds "
           "depends upon the intentions and every person will get the reward according "
           "to what he has intended.\"")


def test_a_contiguous_run_is_verbatim():
    assert english_status("The reward of deeds depends upon the intentions", [DATASET]) == VERBATIM


def test_punctuation_case_and_apostrophes_do_not_matter():
    assert english_status("the reward of deeds, depends upon the Intentions!", [DATASET]) == VERBATIM
    assert english_status("I heard Allahs Messenger saying", [DATASET]) == VERBATIM


def test_inserted_honorifics_do_not_matter():
    assert english_status("Allah's Messenger ﷺ saying", [DATASET]) == VERBATIM
    assert english_status("Allah's Messenger (peace be upon him) saying", [DATASET]) == VERBATIM


def test_verse_numbers_added_to_a_block_do_not_matter():
    assert english_status("(1) sea (2) river", ["sea river"]) == VERBATIM


def test_a_short_elision_is_stitched():
    long_text = " ".join("w%d" % i for i in range(60))
    elided = " ".join("w%d" % i for i in range(60) if i != 30)
    assert english_status(elided, [long_text]) == STITCHED


def test_a_paraphrase_is_own_even_with_the_same_vocabulary():
    assert english_status("Deeds are judged by what a person intended", [DATASET]) == OWN


def test_a_word_inside_a_longer_word_is_not_a_match():
    assert english_status("he", ["the"]) == OWN


def test_no_reference_or_no_words_is_own():
    assert english_status("anything", []) == OWN
    assert english_status("anything", [""]) == OWN
    assert english_status("", [DATASET]) == OWN


def test_any_reference_may_satisfy_it():
    assert english_status("river", ["sea", "river"]) == VERBATIM


def test_words_drops_translit_marks_without_splitting_the_word():
    assert words("ʿAbdullah's") == ["abdullahs"]
