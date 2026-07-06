from ingest.chunk import smart_chunk


def _secs(sizes):
    # build contiguous sections of the given page-sizes, starting at page 1
    out, start = [], 1
    for i, n in enumerate(sizes):
        out.append({"title": "S%d" % i, "start_page": start, "end_page": start + n - 1})
        start += n
    return out


def test_packs_whole_sections_under_target():
    chunks = smart_chunk(_secs([3, 3, 3, 3]), target_pages=7)
    assert [c["page_count"] for c in chunks] == [6, 6]
    assert [c["sections"] for c in chunks] == [["S0", "S1"], ["S2", "S3"]]


def test_oversized_section_becomes_its_own_chunk():
    chunks = smart_chunk(_secs([4, 15, 4]), target_pages=10)
    assert [c["page_count"] for c in chunks] == [4, 15, 4]     # the 15-page section is never split


def test_covers_all_pages_without_gaps_or_overlap():
    chunks = smart_chunk(_secs([3, 3, 3, 3]), target_pages=7)
    pages = []
    for c in chunks:
        pages.extend(range(c["start_page"], c["end_page"] + 1))
    assert pages == list(range(1, 13))                          # 1..12, contiguous, no repeats


def test_context_page_is_prev_page_or_none():
    chunks = smart_chunk(_secs([5, 5]), target_pages=5)
    assert chunks[0]["context_page"] is None                   # first chunk starts at page 1
    assert chunks[1]["context_page"] == 5                       # page before chunk 2's start (6)


def test_single_section():
    chunks = smart_chunk(_secs([8]), target_pages=10)
    assert len(chunks) == 1 and chunks[0]["page_count"] == 8


def test_appendix_flag_emitted_and_never_mixed():
    secs = [{"title": "A", "start_page": 1, "end_page": 4},
            {"title": "B", "start_page": 5, "end_page": 8},
            {"title": "X", "start_page": 9, "end_page": 12, "appendix": True}]
    chunks = smart_chunk(secs, target_pages=20)   # all three would fit one chunk
    assert len(chunks) == 2                        # ...but appendix forces a break
    assert chunks[0]["appendix"] is False and chunks[1]["appendix"] is True
    assert chunks[0]["sections"] == ["A", "B"] and chunks[1]["sections"] == ["X"]


def test_context_page_walks_back_to_nearest_text_page():
    secs = [{"title": "A", "start_page": 1, "end_page": 5},
            {"title": "B", "start_page": 6, "end_page": 10}]
    # page 5 is an ornamental divider -> context must fall back to page 4
    chunks = smart_chunk(secs, target_pages=5, text_pages={1, 2, 3, 4, 6, 7, 8, 9, 10})
    assert chunks[1]["context_page"] == 4


def test_context_page_none_when_no_text_page_before():
    secs = [{"title": "A", "start_page": 3, "end_page": 8}]
    chunks = smart_chunk(secs, target_pages=10, text_pages={5, 6})
    assert chunks[0]["context_page"] is None


def test_skip_sections_excluded_from_chunks():
    secs = [{"title": "A", "start_page": 1, "end_page": 8},
            {"title": "notes", "start_page": 9, "end_page": 12, "skip": True}]
    chunks = smart_chunk(secs, target_pages=10)
    assert len(chunks) == 1 and chunks[0]["end_page"] == 8


def test_same_page_sections_never_straddle_a_chunk_boundary():
    # B ends on page 11 and C starts on page 11 -> the boundary page is shared,
    # so the chunker must not break between them even when over target.
    secs = [{"title": "A", "start_page": 1, "end_page": 10},
            {"title": "B", "start_page": 11, "end_page": 11},
            {"title": "C", "start_page": 11, "end_page": 20}]
    chunks = smart_chunk(secs, target_pages=10)
    assert chunks[0]["sections"] == ["A"]
    assert chunks[1]["sections"] == ["B", "C"]
