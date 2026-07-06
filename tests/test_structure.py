from ingest import structure as st


def test_build_page_ranges_fills_ends():
    secs = [{"title": "A", "start_page": 1, "level": 1},
            {"title": "B", "start_page": 5, "level": 1},
            {"title": "C", "start_page": 9, "level": 1}]
    out = st.build_page_ranges(secs, total_pages=12)
    assert [(s["start_page"], s["end_page"]) for s in out] == [(1, 4), (5, 8), (9, 12)]


def test_build_page_ranges_sorts_by_start():
    secs = [{"title": "B", "start_page": 5, "level": 1},
            {"title": "A", "start_page": 1, "level": 1}]
    out = st.build_page_ranges(secs, total_pages=8)
    assert [s["title"] for s in out] == ["A", "B"]
    assert out[0]["end_page"] == 4 and out[1]["end_page"] == 8


def test_validate_catches_problems():
    assert st.validate_structure([], 10) == ["no sections"]
    bad = [{"title": "A", "start_page": 1, "level": 1},
           {"title": "B", "start_page": 99, "level": 1}]
    probs = st.validate_structure(bad, total_pages=10)
    assert any("out of range" in p for p in probs)


def test_validate_ok():
    good = [{"title": "A", "start_page": 1, "level": 1},
            {"title": "B", "start_page": 5, "level": 1}]
    assert st.validate_structure(good, total_pages=10) == []


def test_skip_sections_bound_previous_section_and_survive():
    # A trailing skip entry marks 'content ends here' (back matter, notebook pages).
    secs = [{"title": "A", "start_page": 1},
            {"title": "B", "start_page": 5},
            {"title": "notes", "start_page": 9, "skip": True}]
    out = st.build_page_ranges(secs, total_pages=12)
    assert [(s["start_page"], s["end_page"]) for s in out] == [(1, 4), (5, 8), (9, 12)]
    assert out[2].get("skip") is True
    assert st.validate_structure(secs, total_pages=12) == []


def test_same_start_page_sections_are_valid_and_keep_input_order():
    # a chapter heading and its first subsection often share one printed page
    secs = [{"title": "Chapter", "start_page": 5},
            {"title": "Sub", "start_page": 5}]
    assert st.validate_structure(secs, total_pages=10) == []
    out = st.build_page_ranges(secs, total_pages=10)
    assert [s["title"] for s in out] == ["Chapter", "Sub"]
    assert out[1]["end_page"] == 10
