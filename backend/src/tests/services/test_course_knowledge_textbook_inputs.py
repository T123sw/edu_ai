from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.persistence.postgres_knowledge_repository import (
    KnowledgeBuildRevisionConflict,
)
from app.services import course_knowledge_textbook_inputs as textbook_inputs
from app.services.course_knowledge_textbook_inputs import (
    CourseKnowledgeTextbookInputError,
    SUPPORTED_TEXTBOOK_EXTENSIONS,
    parse_course_knowledge_textbook,
    remove_course_knowledge_textbook,
    run_course_knowledge_textbook_parse_job,
    stage_course_knowledge_textbook,
)


class FakeManager:
    def __init__(self, root: Path):
        self.root = root

    def get_course_dir(self, course_id: str) -> Path:
        path = self.root / course_id
        path.mkdir(parents=True, exist_ok=True)
        return path


class FakeRepository:
    def __init__(self):
        self.build = {
            "build_id": "kb-1",
            "library_id": "course-1",
            "status": "draft",
            "phase": "draft_config",
            "revision": 1,
            "textbooks": [],
        }

    def get_build(self, build_id):
        return deepcopy(self.build) if build_id == "kb-1" else None

    def update_build_draft(self, build_id, *, expected_revision, changes, phase):
        assert build_id == "kb-1"
        if self.build["revision"] != expected_revision:
            raise KnowledgeBuildRevisionConflict("stale")
        self.build.update(deepcopy(dict(changes)))
        self.build["revision"] += 1
        self.build["phase"] = phase
        return deepcopy(self.build)


def test_supported_textbook_formats_are_exactly_product_contract():
    assert SUPPORTED_TEXTBOOK_EXTENSIONS == {".pdf", ".docx", ".txt", ".md"}


def test_presentation_file_is_not_claimed_as_supported(tmp_path):
    with pytest.raises(CourseKnowledgeTextbookInputError) as raised:
        stage_course_knowledge_textbook(
            manager=FakeManager(tmp_path),
            course_id="course-1",
            build_id="kb-1",
            owner_user_id="teacher-1",
            expected_revision=1,
            filename="教材.pptx",
            file_bytes=b"presentation",
            repository=FakeRepository(),
        )
    assert raised.value.code == "TEXTBOOK_FORMAT_UNSUPPORTED"


def test_stage_textbook_persists_immutable_input_and_deduplicates(tmp_path):
    manager = FakeManager(tmp_path)
    repository = FakeRepository()

    updated, textbook = stage_course_knowledge_textbook(
        manager=manager,
        course_id="course-1",
        build_id="kb-1",
        owner_user_id="teacher-1",
        expected_revision=1,
        filename="教材.md",
        file_bytes=b"# Chapter\n\nContent",
        repository=repository,
    )

    source_path = manager.get_course_dir("course-1") / textbook["relative_path"]
    assert source_path.read_bytes() == b"# Chapter\n\nContent"
    assert textbook["status"] == "queued"
    assert updated["revision"] == 2
    assert updated.get("graph_draft") is None

    with pytest.raises(CourseKnowledgeTextbookInputError) as raised:
        stage_course_knowledge_textbook(
            manager=manager,
            course_id="course-1",
            build_id="kb-1",
            owner_user_id="teacher-1",
            expected_revision=2,
            filename="same-content.md",
            file_bytes=b"# Chapter\n\nContent",
            repository=repository,
        )
    assert raised.value.code == "TEXTBOOK_DUPLICATE"


def test_markdown_parser_extracts_outline_chunks_and_summary(tmp_path):
    path = tmp_path / "poetry.md"
    path.write_text(
        "# 第一章 意象\n\n## 月意象\n\n分析月意象。\n\n# 第二章 语言\n\n分析语言风格。",
        encoding="utf-8",
    )

    result = parse_course_knowledge_textbook(
        path=path,
        filename=path.name,
        textbook_id="book-1",
    )

    assert [item["title"] for item in result["outline"]] == [
        "第一章 意象",
        "第二章 语言",
    ]
    assert result["outline"][0]["sections"][0]["title"] == "月意象"
    assert result["chunk_count"] == 2
    assert "分析月意象" in result["summary"]


def test_pdf_parser_is_used_without_rag_import(tmp_path):
    path = tmp_path / "book.pdf"
    path.write_bytes(b"fake-pdf")

    class PdfParser:
        def parse(self, payload, *, filename):
            assert payload == b"fake-pdf"
            assert filename == "book.pdf"
            return SimpleNamespace(
                text="# 第一章 证据阅读\n\n正文",
                metadata={"parser": "fake-mineru", "pageCount": 1},
            )

    result = parse_course_knowledge_textbook(
        path=path,
        filename="book.pdf",
        textbook_id="book-1",
        pdf_parser=PdfParser(),
    )

    assert result["parser"] == "fake-mineru"
    assert result["chapter_count"] == 1


def test_parse_job_updates_only_build_draft_and_keeps_original(tmp_path, monkeypatch):
    manager = FakeManager(tmp_path)
    repository = FakeRepository()
    updated, textbook = stage_course_knowledge_textbook(
        manager=manager,
        course_id="course-1",
        build_id="kb-1",
        owner_user_id="teacher-1",
        expected_revision=1,
        filename="教材.txt",
        file_bytes="# 诗歌意象\n\n意象正文".encode("utf-8"),
        repository=repository,
    )
    job_updates = []
    monkeypatch.setattr(
        textbook_inputs,
        "update_job",
        lambda job_id, **fields: job_updates.append((job_id, fields)),
    )

    result = run_course_knowledge_textbook_parse_job(
        manager=manager,
        job_id="job-1",
        course_id="course-1",
        build_id="kb-1",
        textbook_id=textbook["textbook_id"],
        repository=repository,
    )

    current = repository.get_build("kb-1")
    assert updated["revision"] == 2
    assert current["textbooks"][0]["status"] == "ready"
    assert current["textbooks"][0]["parse_result"]["chapter_count"] == 1
    assert result["revision"] == current["revision"]
    assert job_updates[-1][1]["status"].value == "succeeded"
    assert (
        manager.get_course_dir("course-1") / textbook["relative_path"]
    ).is_file()


def test_remove_textbook_changes_draft_but_retains_recoverable_file(tmp_path):
    manager = FakeManager(tmp_path)
    repository = FakeRepository()
    updated, textbook = stage_course_knowledge_textbook(
        manager=manager,
        course_id="course-1",
        build_id="kb-1",
        owner_user_id="teacher-1",
        expected_revision=1,
        filename="教材.md",
        file_bytes=b"# Content",
        repository=repository,
    )
    source_path = manager.get_course_dir("course-1") / textbook["relative_path"]

    removed = remove_course_knowledge_textbook(
        course_id="course-1",
        build_id="kb-1",
        textbook_id=textbook["textbook_id"],
        expected_revision=updated["revision"],
        repository=repository,
    )

    assert removed["textbooks"] == []
    assert source_path.is_file()
