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


def test_char_count_ignores_tatweel_ruled_pages():
    # "al-Mufakkirah" notes pages are rows of kashida/tatweel (ـ), which is alnum in
    # Unicode but not content -> a header word must be all that counts
    assert pages._char_count("ـ" * 300) == 0
    assert pages._char_count("المفكرة " + "ـ" * 120) == 7   # only the 7 header letters


def test_analyze_book_extracts_text_in_one_pass(monkeypatch):
    calls = []

    def fake_run(cmd):
        calls.append(cmd)
        if cmd[0] == "pdfinfo":
            return "Pages:          3\n"
        if cmd[0] == "pdftotext":
            return "first page words here\f\fكلمات الصفحة الثالثة هنا يا صاحبي المفضال\f"
        if cmd[0] == "pdffonts":
            return "name  type\n----  ----\nCardo  CID\n"
        return ""

    monkeypatch.setattr(pages, "_run", fake_run)
    book = pages.analyze_book("x.pdf")
    assert book["total_pages"] == 3
    assert [p["page"] for p in book["pages"]] == [1, 2, 3]
    assert book["pages"][1]["chars"] == 0                      # the empty middle page
    assert book["pages"][1]["classification"] == "ornamental"
    assert book["pages"][2]["chars"] > 30
    assert len([c for c in calls if c[0] == "pdftotext"]) == 1   # ONE whole-doc call
    assert len([c for c in calls if c[0] == "pdffonts"]) == 3    # still per page


def test_analyze_book_falls_back_when_formfeeds_disagree(monkeypatch):
    # a PDF whose text layer embeds stray form-feeds defeats the split -> per-page path
    def fake_run(cmd):
        if cmd[0] == "pdfinfo":
            return "Pages: 2\n"
        if cmd[0] == "pdftotext":
            if "-f" in cmd:
                return "per page %s text" % cmd[cmd.index("-f") + 1]
            return "a\fb\fc\fd"   # 4 parts, expected 2 (+ trailing)
        return ""

    monkeypatch.setattr(pages, "_run", fake_run)
    book = pages.analyze_book("x.pdf")
    assert book["total_pages"] == 2 and len(book["pages"]) == 2
    assert all(p["chars"] > 0 for p in book["pages"])   # per-page texts were used
