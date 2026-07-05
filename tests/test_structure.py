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
