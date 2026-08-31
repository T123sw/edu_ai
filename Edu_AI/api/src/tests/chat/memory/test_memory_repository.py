from sqlalchemy import create_engine

from app.chat.memory.domain import MemoryRecordDraft
from app.chat.memory.repository import SqlAlchemyMemoryRepository
from app.database import Base


def _repository() -> SqlAlchemyMemoryRepository:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return SqlAlchemyMemoryRepository(engine)


def test_repository_deduplicates_and_scopes_memories() -> None:
    repository = _repository()
    draft = MemoryRecordDraft(
        subject_user_id="alice",
        owner_user_id="alice",
        course_id="course-a",
        conversation_id="conv-1",
        memory_type="preference",
        fact_kind="preference",
        content="用户偏好使用生活化例子",
        confidence=0.95,
        source_type="conversation",
        source_id="conv-1:1",
        source_span="我喜欢生活化例子",
        profile_axis="learning_style",
    )

    first = repository.upsert_memory(draft)
    second = repository.upsert_memory(
        draft.model_copy(update={"source_id": "conv-2:1"})
    )

    assert first.memory_id == second.memory_id
    assert second.evidence_count == 2
    assert repository.search(
        subject_user_id="alice", course_id="course-a", query="生活化例子", limit=5
    )
    assert (
        repository.search(
            subject_user_id="bob", course_id="course-a", query="生活化例子", limit=5
        )
        == []
    )
    assert (
        repository.search(
            subject_user_id="alice", course_id="course-b", query="生活化例子", limit=5
        )
        == []
    )


def test_repository_correction_supersedes_previous_profile_fact() -> None:
    repository = _repository()
    base = MemoryRecordDraft(
        subject_user_id="alice",
        owner_user_id="alice",
        memory_type="preference",
        fact_kind="preference",
        content="用户偏好详细回答",
        confidence=0.95,
        source_type="conversation",
        source_id="conv-1:1",
        source_span="请详细回答",
        profile_axis="response_detail",
    )
    old = repository.upsert_memory(base)
    new = repository.upsert_memory(
        base.model_copy(
            update={
                "content": "用户偏好简短回答",
                "source_id": "conv-2:1",
                "source_span": "以后请简短回答",
                "supersedes_axis": True,
            }
        )
    )

    assert new.memory_id != old.memory_id
    assert repository.get(old.memory_id).status == "superseded"
    assert (
        repository.list_profile_facts(subject_user_id="alice")[0].value
        == "用户偏好简短回答"
    )


def test_profile_can_be_invalidated_recreated_and_invalidated_again() -> None:
    repository = _repository()
    base = MemoryRecordDraft(
        subject_user_id="alice",
        owner_user_id="alice",
        memory_type="preference",
        fact_kind="preference",
        content="用户偏好详细回答",
        confidence=0.95,
        source_type="conversation",
        source_id="conv-1:1",
        source_span="请详细回答",
        profile_axis="response_detail",
    )
    first = repository.upsert_memory(base)
    assert repository.invalidate(
        memory_id=first.memory_id, subject_user_id="alice", reason="changed mind"
    )

    second = repository.upsert_memory(
        base.model_copy(
            update={
                "content": "用户偏好简短回答",
                "source_id": "conv-2:1",
                "source_span": "请简短回答",
                "supersedes_axis": True,
            }
        )
    )
    assert repository.invalidate(
        memory_id=second.memory_id, subject_user_id="alice", reason="changed again"
    )
    assert repository.list_profile_facts(subject_user_id="alice") == []
