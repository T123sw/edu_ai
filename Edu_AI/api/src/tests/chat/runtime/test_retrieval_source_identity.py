from app.chat.runtime.nodes.tools import _retrieval_source_key


def test_retrieval_source_key_keeps_distinct_chunks_from_same_document():
    first = {
        "chunk_id": "doc-a:chunk-1",
        "source": "lesson.md",
        "content": "first chunk",
    }
    second = {
        "chunk_id": "doc-a:chunk-2",
        "source": "lesson.md",
        "content": "second chunk",
    }

    assert _retrieval_source_key(first) != _retrieval_source_key(second)


def test_retrieval_source_key_deduplicates_the_same_chunk():
    source = {
        "chunk_id": "doc-a:chunk-1",
        "source": "lesson.md",
        "content": "same chunk",
    }

    assert _retrieval_source_key(source) == _retrieval_source_key(dict(source))


def test_retrieval_source_key_fallback_uses_content_when_chunk_id_is_missing():
    first = {"source": "lesson.md", "content": "first chunk"}
    second = {"source": "lesson.md", "content": "second chunk"}

    assert _retrieval_source_key(first) != _retrieval_source_key(second)
