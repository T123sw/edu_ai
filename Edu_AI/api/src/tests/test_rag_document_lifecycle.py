import sys
from pathlib import Path

import pytest

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.services import knowledge_document_service as service
from app.services import job_store
from app.services.job_store import JobStatus
from core import Config
from core.course_storage import CourseStorageManager


class FakeVectorStore:
    def __init__(self):
        self.documents = []

    def get_documents_by_source(self, source):
        return [item for item in self.documents if item["metadata"]["source"] == source]

    def hybrid_search(self, query, query_embedding, top_k, allowed_sources=None, **kwargs):
        candidates = self.documents
        if allowed_sources:
            candidates = [
                item for item in candidates if item["metadata"]["source"] in allowed_sources
            ]
        ranked = sorted(candidates, key=lambda item: "快速排序" not in item["content"])
        return [{**item, "rrf_score": 0.02} for item in ranked[:top_k]]


class FakeEmbeddingClient:
    model = "test-embedding-v1"

    @staticmethod
    def embed_query(text):
        return [1.0]


class FakeRagSystem:
    def __init__(self, *, fail=False):
        self.fail = fail
        self.document_index = {}
        self.vector_store = FakeVectorStore()
        self.embedding_client = FakeEmbeddingClient()

    def _make_index_key(self, path, owner):
        return f"user_{owner}:{Path(path).resolve()}"

    def _make_source_key(self, path, owner):
        return self._make_index_key(path, owner)

    def list_documents(self, owner=None):
        return [
            {
                "file_path": key,
                "file_name": value["file_name"],
                "owner": value["owner"],
            }
            for key, value in self.document_index.items()
            if owner is None or value["owner"] == owner
        ]

    def retrieve_documents(
        self,
        question,
        *,
        top_k=5,
        allowed_sources=None,
        rewritten_query=None,
        query_embedding=None,
    ):
        return self.vector_store.hybrid_search(
            question,
            self.embedding_client.embed_query(question),
            top_k,
            allowed_sources=allowed_sources,
        )

    def import_document(
        self,
        path,
        force_reimport=False,
        progress_callback=None,
        owner=None,
        metadata_overrides=None,
    ):
        progress_callback(15, "loading_pdf")
        progress_callback(50, "embedding")
        if self.fail:
            raise RuntimeError("embedding unavailable")
        key = self._make_index_key(path, owner)
        self.document_index[key] = {
            "physical_path": str(Path(path).resolve()),
            "source_key": key,
            "file_name": Path(path).name,
            "owner": owner,
            "chunk_count": 2,
            "page_count": 1,
        }
        self.vector_store.documents = [
            {
                "id": "chunk-1",
                "content": "快速排序通过选择基准并递归处理左右分区完成分治。",
                "metadata": {"source": key, "page": "0", **(metadata_overrides or {})},
            },
            {
                "id": "chunk-2",
                "content": "冒泡排序会反复交换相邻的逆序元素。",
                "metadata": {"source": key, "page": "0", **(metadata_overrides or {})},
            },
        ]
        progress_callback(100, "completed")
        return {"status": "success", "chunk_count": 2}


@pytest.fixture()
def document_fixture(monkeypatch, tmp_path):
    from app.chat.tasks.task_store import TaskStore

    monkeypatch.setattr(Config, "STORAGE_ROOT", tmp_path / "job-storage")
    manager = CourseStorageManager(str(tmp_path / "courses"))
    manager.create_course_structure("course-1")
    manager.save_course_info(
        "course-1",
        {
            "id": "course-1",
            "title": "算法",
            "description": "",
            "icon": "",
            "color": "",
        },
    )
    manager.save_knowledge_base_file(
        "course-1",
        "# 快速排序".encode("utf-8"),
        "sorting.md",
        owner_user_id="teacher-a",
        library_type="personal",
    )
    document_id = manager.get_knowledge_base_index("course-1")[0]["id"]
    service.initialize_document(manager, "course-1", document_id)
    task_store = TaskStore(str(tmp_path / "tasks.db"))
    monkeypatch.setattr(
        "app.services.platform_task_handlers.get_task_store",
        lambda: task_store,
    )
    yield manager, document_id, task_store
    task_store.close()


@pytest.mark.anyio
async def test_upload_index_lifecycle_becomes_ready_and_retrievable(document_fixture):
    manager, document_id, task_store = document_fixture
    rag = FakeRagSystem()
    job = service.submit_index_job(
        manager=manager,
        rag_system=rag,
        course_id="course-1",
        document_id=document_id,
        owner_user_id="teacher-a",
        force_reindex=False,
    )

    durable = task_store.get_durable(job.edu_job_id)
    assert durable is not None
    service.run_index_job(
        manager=manager,
        rag_system=rag,
        course_id="course-1",
        document_id=document_id,
        owner_user_id="teacher-a",
        force_reindex=False,
        pending_version=durable.command["pending_version"],
        job_id=job.edu_job_id,
    )
    assert job_store.get_job(job.edu_job_id).status == JobStatus.SUCCEEDED

    document = service.get_document(
        manager, "course-1", document_id, owner_user_id="teacher-a"
    )
    assert document["status"] == "ready"
    assert document["chunk_count"] == 2
    assert document["active_index_version"]
    assert document["pending_index_version"] is None
    assert document["last_job_id"] == job.edu_job_id
    assert all(
        chunk["metadata"]["library_type"] == "personal"
        for chunk in rag.vector_store.documents
    )

    result = service.test_retrieval(
        manager=manager,
        rag_system=rag,
        course_id="course-1",
        document_id=document_id,
        owner_user_id="teacher-a",
        query="快速排序如何分治",
        top_k=1,
    )
    assert result["hits"][0]["chunk_id"] == "chunk-1"
    assert result["hits"][0]["page"] == 1


def test_document_lookup_aggregates_leaf_knowledge_point_scope():
    class LeafScopedManager:
        def get_knowledge_base_index(self, course_id, *, aggregate=False):
            assert course_id == "course-1"
            if not aggregate:
                return []
            return [
                {
                    "id": "leaf-doc",
                    "library_type": "course",
                    "scope_type": "knowledge_point",
                    "scope_id": "leaf-1",
                }
            ]

    document = service.get_document(
        LeafScopedManager(), "course-1", "leaf-doc", owner_user_id="student-a"
    )

    assert document is not None
    assert document["scope_id"] == "leaf-1"


@pytest.mark.anyio
async def test_failed_reindex_preserves_the_active_version(document_fixture):
    manager, document_id, task_store = document_fixture
    service.patch_document(
        manager,
        "course-1",
        document_id,
        status="ready",
        active_index_version="idx_active",
        rag_index_key="existing",
    )
    rag = FakeRagSystem(fail=True)
    job = service.submit_index_job(
        manager=manager,
        rag_system=rag,
        course_id="course-1",
        document_id=document_id,
        owner_user_id="teacher-a",
        force_reindex=True,
    )

    durable = task_store.get_durable(job.edu_job_id)
    assert durable is not None
    service.run_index_job(
        manager=manager,
        rag_system=rag,
        course_id="course-1",
        document_id=document_id,
        owner_user_id="teacher-a",
        force_reindex=True,
        pending_version=durable.command["pending_version"],
        job_id=job.edu_job_id,
    )
    assert job_store.get_job(job.edu_job_id).status == JobStatus.FAILED

    document = service.get_document(
        manager, "course-1", document_id, owner_user_id="teacher-a"
    )
    assert document["status"] == "ready"
    assert document["active_index_version"] == "idx_active"
    assert document["pending_index_version"] is None
    assert document["error_code"] == "RAG_INDEX_FAILED"


def test_ready_document_keeps_public_id_when_rag_key_changes(document_fixture):
    manager, document_id, _task_store = document_fixture

    first = service.mark_document_ready(
        manager,
        "course-1",
        document_id,
        rag_index_key="rag/key/1",
        chunk_count=12,
    )
    second = service.mark_document_ready(
        manager,
        "course-1",
        document_id,
        rag_index_key="rag/key/2",
        chunk_count=15,
    )

    assert first["id"] == document_id
    assert second["id"] == document_id
    assert second["rag_index_key"] == "rag/key/2"
    assert second["chunk_count"] == 15
