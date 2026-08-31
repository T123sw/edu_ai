from __future__ import annotations

from app.services.course_knowledge_coverage import calculate_leaf_coverage


TOPICS = [{"topic_id": "leaf", "title": "一元方程"}]


def test_long_textbook_and_web_source_satisfy_three_coverage_units():
    result = calculate_leaf_coverage(
        TOPICS,
        [
            {
                "document_id": "book-leaf",
                "scope_id": "leaf",
                "source_type": "textbook",
                "source_artifact_id": "book-1",
                "content_hash": "book-hash",
                "content_chars": 5000,
                "mapping_confidence": 0.8,
                "provenance_ok": True,
                "is_online_textbook": True,
            },
            {
                "document_id": "web-1",
                "scope_id": "leaf",
                "source_type": "web",
                "content_hash": "web-hash",
                "content_chars": 1200,
                "provenance_ok": True,
            },
        ],
        target_units=3,
        minimum_external_sources=1,
        maximum_ai=1,
    )

    leaf = result["leaf"]
    assert leaf["textbook_units"] == 2
    assert leaf["web_units"] == 1
    assert leaf["effective_units"] == 3
    assert leaf["external_sources"] == 2
    assert leaf["unmet"] == []


def test_low_confidence_short_and_duplicate_materials_do_not_inflate_coverage():
    result = calculate_leaf_coverage(
        TOPICS,
        [
            {
                "document_id": "low-confidence-book",
                "scope_id": "leaf",
                "source_type": "textbook",
                "source_artifact_id": "book-1",
                "content_hash": "book-low",
                "content_chars": 6000,
                "mapping_confidence": 0.2,
                "provenance_ok": True,
            },
            {
                "document_id": "web-short",
                "scope_id": "leaf",
                "source_type": "web",
                "content_hash": "same",
                "content_chars": 300,
                "provenance_ok": True,
            },
            {
                "document_id": "web-duplicate",
                "scope_id": "leaf",
                "source_type": "web",
                "content_hash": "same",
                "content_chars": 1500,
                "provenance_ok": True,
            },
            {
                "document_id": "ai-1",
                "scope_id": "leaf",
                "source_type": "model_generated",
                "content_hash": "ai-hash",
                "content_chars": 900,
            },
        ],
        target_units=3,
        minimum_external_sources=1,
        maximum_ai=1,
    )

    leaf = result["leaf"]
    assert leaf["textbook_units"] == 0
    assert leaf["web_units"] == 0
    assert leaf["ai_units"] == 1
    assert leaf["effective_units"] == 1
    assert leaf["external_sources"] == 0
    assert leaf["rejected_materials"] == 3
    assert "有效覆盖 1/3" in leaf["unmet"]
    assert "外部来源 0/1" in leaf["unmet"]


def test_one_textbook_artifact_is_capped_at_two_units_per_leaf():
    result = calculate_leaf_coverage(
        TOPICS,
        [
            {
                "document_id": f"book-part-{index}",
                "scope_id": "leaf",
                "source_type": "textbook",
                "source_artifact_id": "book-1",
                "content_hash": f"book-{index}",
                "content_chars": 4500,
                "mapping_confidence": 0.9,
                "provenance_ok": True,
            }
            for index in range(3)
        ],
        target_units=3,
        minimum_external_sources=1,
        maximum_ai=0,
    )

    assert result["leaf"]["textbook_units"] == 2
    assert result["leaf"]["effective_units"] == 2
