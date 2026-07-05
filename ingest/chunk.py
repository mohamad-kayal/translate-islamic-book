"""Smart chunking: pack whole sections into chunks, never splitting a section."""


def _close(secs):
    start, end = secs[0]["start_page"], secs[-1]["end_page"]
    return {
        "sections": [s["title"] for s in secs],
        "start_page": start,
        "end_page": end,
        "page_count": end - start + 1,
        "context_page": start - 1 if start > 1 else None,
    }


def smart_chunk(sections, target_pages=10):
    """sections: [{title, start_page, end_page}] in reading order. Returns chunks, each a
    run of whole sections whose combined length stays near target_pages (a single section
    longer than target becomes its own chunk). A section is never split across chunks."""
    chunks, cur, cur_pages = [], [], 0
    for sec in sections:
        sec_pages = sec["end_page"] - sec["start_page"] + 1
        if cur and cur_pages + sec_pages > target_pages:
            chunks.append(_close(cur))
            cur, cur_pages = [], 0
        cur.append(sec)
        cur_pages += sec_pages
    if cur:
        chunks.append(_close(cur))
    return chunks
