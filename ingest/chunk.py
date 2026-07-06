"""Smart chunking: pack whole sections into chunks, never splitting a section."""


def _close(secs, text_pages=None):
    start, end = secs[0]["start_page"], secs[-1]["end_page"]
    ctx = start - 1
    if text_pages is not None:
        # skip back over ornamental dividers / blank pages: the context page exists
        # to give the subagent continuity, which a divider cannot provide.
        while ctx >= 1 and ctx not in text_pages:
            ctx -= 1
    return {
        "sections": [s["title"] for s in secs],
        "start_page": start,
        "end_page": end,
        "page_count": end - start + 1,
        "context_page": ctx if ctx >= 1 else None,
        "appendix": bool(secs[0].get("appendix")),
    }


def smart_chunk(sections, target_pages=10, text_pages=None):
    """sections: [{title, start_page, end_page, appendix?, skip?}] in reading order.
    Returns chunks, each a run of whole sections whose combined length stays near
    target_pages (a single section longer than target becomes its own chunk).
    A section is never split across chunks; main-body and appendix sections are
    never mixed in one chunk; sections sharing a printed page stay together;
    skip=true sections (back matter) are excluded entirely."""
    sections = [s for s in sections if not s.get("skip")]
    chunks, cur, cur_pages = [], [], 0
    for sec in sections:
        sec_pages = max(0, sec["end_page"] - sec["start_page"] + 1)
        if cur:
            flag_change = bool(sec.get("appendix")) != bool(cur[0].get("appendix"))
            over_target = cur_pages + sec_pages > target_pages
            # sections sharing the boundary page must stay in one chunk
            clean_boundary = sec["start_page"] > cur[-1]["end_page"]
            if flag_change or (over_target and clean_boundary):
                chunks.append(_close(cur, text_pages))
                cur, cur_pages = [], 0
        cur.append(sec)
        cur_pages += sec_pages
    if cur:
        chunks.append(_close(cur, text_pages))
    return chunks
