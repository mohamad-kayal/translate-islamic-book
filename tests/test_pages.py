from ingest import pages


def test_classify_threshold():
    assert pages.classify(0) == "ornamental"
    assert pages.classify(29) == "ornamental"
    assert pages.classify(30) == "text"
    assert pages.classify(2000) == "text"


def test_char_count_ignores_whitespace():
    assert pages._char_count("  ab \n c d\t") == len("abcd")


def test_char_count_counts_only_letters_and_digits():
    # ruled notebook pages are rows of underscores -> must classify ornamental
    assert pages._char_count("____" * 200) == 0
    assert pages._char_count("أبج 12 ___ ‏") == 5
