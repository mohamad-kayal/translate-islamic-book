import json

from scripts.run_status import chunk_state


def _work(tmp_path, n_chunks, done):
    work = tmp_path / "work"
    (work / "translated").mkdir(parents=True)
    chunks = [{"sections": ["S%d" % i], "start_page": i, "end_page": i}
              for i in range(1, n_chunks + 1)]
    (work / "chunks.json").write_text(json.dumps(chunks))
    for i in done:
        (work / "translated" / ("chunk_%04d.md" % i)).write_text("# translated\n")
    return str(work)


def test_chunk_state_partial(tmp_path):
    assert chunk_state(_work(tmp_path, 4, done=[1, 3])) == {
        "total": 4, "done": [1, 3], "missing": [2, 4]}


def test_chunk_state_complete(tmp_path):
    state = chunk_state(_work(tmp_path, 2, done=[1, 2]))
    assert state["missing"] == [] and state["done"] == [1, 2]


def test_chunk_state_nothing_translated_yet(tmp_path):
    state = chunk_state(_work(tmp_path, 3, done=[]))
    assert state["done"] == [] and state["missing"] == [1, 2, 3]


def test_chunk_state_empty_file_counts_as_missing(tmp_path):
    work = _work(tmp_path, 2, done=[1])
    (tmp_path / "work" / "translated" / "chunk_0002.md").write_text("")
    assert chunk_state(work)["missing"] == [2]


def test_chunk_state_not_chunked(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    assert chunk_state(str(work)) == {"not_chunked": True}
