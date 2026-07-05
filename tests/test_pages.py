from ingest import pages


def test_classify_threshold():
    assert pages.classify(0) == "ornamental"
    assert pages.classify(29) == "ornamental"
    assert pages.classify(30) == "text"
    assert pages.classify(2000) == "text"


def test_char_count_ignores_whitespace():
    assert pages._char_count("  ab \n c d\t") == len("abcd")
