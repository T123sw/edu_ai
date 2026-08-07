import sys
from pathlib import Path
import uuid

import pytest

API_ROOT = Path(__file__).resolve().parents[2]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app import courses
from app.api import courses as courses_api
from app.services.course_access import CoursePrincipal
from app.services import course_service


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _make_workspace_tmp(name: str) -> Path:
    base_dir = Path(__file__).resolve().parents[5] / "_runtime_import_test_tmp_root"
    base_dir.mkdir(parents=True, exist_ok=True)
    test_dir = base_dir / f"{name}_{uuid.uuid4().hex}"
    test_dir.mkdir(parents=True, exist_ok=True)
    return test_dir


class FakeCourseManager:
    def __init__(self, root: Path):
        self.root = root
        self.index = []

    def get_course_info(self, course_id):
        return {"id": course_id}

    def get_course_dir(self, course_id):
        course_dir = self.root / course_id
        course_dir.mkdir(parents=True, exist_ok=True)
        return course_dir

    def save_knowledge_base_file(self, course_id, file_data, filename, **kwargs):
        relative_path = Path("knowledge_base") / filename
        full_path = self.get_course_dir(course_id) / relative_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_bytes(file_data)
        self.index.append(
            {
                "id": f"kb-{len(self.index) + 1}",
                "filename": filename,
                "path": relative_path.as_posix(),
                "uploaded_at": "2026-04-15T00:00:00",
                "scope_type": kwargs.get("scope_type", "course"),
                "scope_id": kwargs.get("scope_id"),
            }
        )
        return relative_path.as_posix()

    def get_knowledge_base_index(self, course_id):
        return list(self.index)

    def save_knowledge_base_index(self, course_id, records):
        self.index = list(records)
        return True


class FakeJob:
    def model_dump(self, mode="json"):
        return {"edu_job_id": "job-test", "kind": "rag_import", "status": "queued"}


class FakeRAGSystem:
    def __init__(self, physical_path: Path, owner: str):
        self.physical_path = str(physical_path)
        self.owner = owner
        self.index_key = f"user_{owner}:{self.physical_path}"
        self.document_index = {
            self.index_key: {
                "physical_path": self.physical_path,
                "source_key": self.index_key,
                "file_name": physical_path.name,
                "owner": owner,
            }
        }
        self.imported_paths = []

    def _make_index_key(self, file_path, owner):
        if str(file_path).startswith("user_"):
            return str(file_path)
        return f"user_{owner}:{file_path}" if owner else str(file_path)

    def _make_source_key(self, file_path, owner):
        return self._make_index_key(file_path, owner)

    def list_documents(self, owner=None):
        if owner is not None and owner != self.owner:
            return []
        return [{"file_path": self.index_key, "file_name": Path(self.physical_path).name, "owner": self.owner}]

    def import_document(self, file_path, force_reimport=False):
        self.imported_paths.append(file_path)
        return {"status": "success", "file": file_path, "chunk_count": 1}


@pytest.mark.anyio
async def test_add_rag_document_to_course_accepts_public_index_key(monkeypatch):
    tmp_path = _make_workspace_tmp("courses_rag_resolution")
    rag_file = tmp_path / "rag-source" / "lesson.md"
    rag_file.parent.mkdir(parents=True, exist_ok=True)
    rag_file.write_text("lesson content", encoding="utf-8")
    rag_system = FakeRAGSystem(rag_file, owner="alice")
    manager = FakeCourseManager(tmp_path / "courses")

    monkeypatch.setattr(course_service, "_get_manager", lambda: manager)
    monkeypatch.setattr(courses_api, "get_rag_system", lambda: rag_system)
    monkeypatch.setattr(
        courses_api._knowledge,
        "submit_index_job",
        lambda **_kwargs: FakeJob(),
    )

    result = await courses.add_rag_document_to_course_kb(
        "course-1",
        courses.AddRAGDocumentRequest(rag_file_path=rag_system.index_key),
        principal=CoursePrincipal(
            course_id="course-1",
            user_id="alice",
            system_role="teacher",
            course_role="editor",
        ),
    )

    document = result["document"]
    assert document.name == "lesson.md"
    assert document.file_path is None
    saved_path = manager.get_course_dir("course-1") / "knowledge_base" / "lesson.md"
    assert saved_path.read_text(encoding="utf-8") == "lesson content"
