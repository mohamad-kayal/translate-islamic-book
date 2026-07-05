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
