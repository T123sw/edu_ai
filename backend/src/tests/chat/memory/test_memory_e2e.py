from sqlalchemy import create_engine
from threading import Event
import time

from app.chat.memory.langmem_adapter import LangMemAdapter
from app.chat.memory.domain import CandidateExtractionResult, MemoryCandidate
from app.chat.memory.repository import SqlAlchemyMemoryRepository
from app.chat.memory.service import AgentMemoryService
from app.chat.memory.settings import AgentMemorySettings
from app.database import Base


def _service() -> AgentMemoryService:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    settings = AgentMemorySettings(
        enabled=True,
        langmem_enabled=False,
        shadow_mode=False,
        embedding_enabled=False,
    )
    return AgentMemoryService(
        repository=SqlAlchemyMemoryRepository(engine),
        settings=settings,
        langmem_adapter=LangMemAdapter(settings=settings),
    )


def test_cross_conversation_preference_is_written_and_recalled() -> None:
    service = _service()
    write = service.persist_turn(
        actor={"user_id": "student-1", "role": "student"},
        conversation_id="conv-1",
        course_id="course-a",
        user_message="我更喜欢用生活中的例子来理解抽象概念",
        assistant_message="好的，我会记住。",
        agent_state={},
        tool_events=[],
    )

    context = service.read_for_agent(
        actor={"user_id": "student-1", "role": "student"},
        conversation_id="conv-2",
        course_id="course-a",
        task_id=None,
        query="请解释一下递归",
        token_budget=800,
    )

    assert write.written_count == 1
    assert context.profile_facts
    assert "生活" in context.profile_facts[0].value
    assert "生活" in service.build_prompt(context)


def test_shadow_mode_records_decision_but_does_not_write() -> None:
    service = _service()
    service.settings.shadow_mode = True

    result = service.persist_turn(
        actor={"user_id": "teacher-1", "role": "teacher"},
        conversation_id="conv-1",
        course_id="course-a",
        user_message="以后课件请使用简洁风格",
        assistant_message="明白。",
        agent_state={},
        tool_events=[],
    )

    assert result.written_count == 0
    assert result.shadow_candidate_count == 1
    assert service.repository.list_profile_facts(subject_user_id="teacher-1") == []


def test_private_memory_never_crosses_users() -> None:
    service = _service()
    service.persist_turn(
        actor={"user_id": "student-1", "role": "student"},
        conversation_id="conv-1",
        course_id="course-a",
        user_message="请记住我偏好先给提示，不要直接给答案",
        assistant_message="好的。",
        agent_state={},
        tool_events=[],
    )

    other = service.read_for_agent(
        actor={"user_id": "student-2", "role": "student"},
        conversation_id="conv-2",
        course_id="course-a",
        task_id=None,
        query="提示",
        token_budget=800,
    )

    assert other.profile_facts == []
    assert other.conversation_memories == []


def test_conversation_episode_is_recalled_only_in_its_course() -> None:
    class EpisodeAdapter:
        def extract_candidates(self, **kwargs):
            return CandidateExtractionResult(
                provider="langmem",
                status="ok",
                candidates=[
                    MemoryCandidate(
                        memory_type="episode",
                        content="用户上次在数据结构课程中卡在递归终止条件",
                        confidence=0.93,
                        source_span="我还是不明白递归什么时候停止",
                        reason="可复用的课程内对话片段",
                    )
                ],
            )

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    settings = AgentMemorySettings(
        enabled=True,
        langmem_enabled=True,
        langmem_background=False,
        embedding_enabled=False,
    )
    service = AgentMemoryService(
        repository=SqlAlchemyMemoryRepository(engine),
        settings=settings,
        langmem_adapter=EpisodeAdapter(),
    )
    service.persist_turn(
        actor={"user_id": "student-1", "role": "student"},
        conversation_id="conv-course-a",
        course_id="course-a",
        user_message="我还是不明白递归什么时候停止",
        assistant_message="我们从终止条件重新看。",
        agent_state={},
        tool_events=[],
    )

    same_course = service.read_for_agent(
        actor={"user_id": "student-1"},
        conversation_id="conv-new-a",
        course_id="course-a",
        task_id=None,
        query="递归终止条件",
        token_budget=800,
    )
    other_course = service.read_for_agent(
        actor={"user_id": "student-1"},
        conversation_id="conv-new-b",
        course_id="course-b",
        task_id=None,
        query="递归终止条件",
        token_budget=800,
    )

    assert [item.memory_type for item in same_course.conversation_memories] == [
        "episode"
    ]
    assert other_course.conversation_memories == []


def test_provider_candidate_without_exact_source_span_is_rejected() -> None:
    class HallucinatedSourceAdapter:
        def extract_candidates(self, **kwargs):
            return CandidateExtractionResult(
                provider="langmem",
                status="ok",
                candidates=[
                    MemoryCandidate(
                        memory_type="profile_fact",
                        content="用户希望被称为小唐",
                        confidence=0.99,
                        source_span="以后请叫我小唐",
                        reason="claimed source is absent",
                        profile_axis="display_name",
                    )
                ],
            )

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    settings = AgentMemorySettings(
        enabled=True,
        langmem_enabled=True,
        langmem_background=False,
        embedding_enabled=False,
    )
    service = AgentMemoryService(
        repository=SqlAlchemyMemoryRepository(engine),
        settings=settings,
        langmem_adapter=HallucinatedSourceAdapter(),
    )

    result = service.persist_turn(
        actor={"user_id": "student-1"},
        conversation_id="conv-source",
        course_id="course-a",
        user_message="请解释一下递归",
        assistant_message="好的。",
        agent_state={},
        tool_events=[],
    )

    assert result.written_count == 0
    assert result.rejected_count == 1
    assert result.decisions[0].reason == "source_span_not_found"


def test_background_langmem_does_not_block_turn_persistence() -> None:
    release = Event()

    class BlockingAdapter:
        def extract_candidates(self, **kwargs):
            release.wait(timeout=2)
            return CandidateExtractionResult(provider="langmem", status="ok")

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    settings = AgentMemorySettings(
        enabled=True,
        langmem_enabled=True,
        langmem_background=True,
        embedding_enabled=False,
    )
    service = AgentMemoryService(
        repository=SqlAlchemyMemoryRepository(engine),
        settings=settings,
        langmem_adapter=BlockingAdapter(),
    )

    started = time.perf_counter()
    result = service.persist_turn(
        actor={"user_id": "student-1", "role": "student"},
        conversation_id="conv-bg",
        course_id="course-a",
        user_message="我更喜欢简短回答",
        assistant_message="好的。",
        agent_state={},
        tool_events=[],
    )
    elapsed = time.perf_counter() - started
    release.set()

    assert elapsed < 0.5
    assert result.provider_status == "scheduled"
    assert result.written_count == 1


def test_user_can_confirm_and_replace_profile_fact() -> None:
    service = _service()
    first = service.confirm_profile_fact(
        actor={"user_id": "student-1"},
        profile_axis="response_detail",
        value="用户偏好详细回答",
    )
    second = service.confirm_profile_fact(
        actor={"user_id": "student-1"},
        profile_axis="response_detail",
        value="用户偏好简短回答",
    )

    assert first.memory_id != second.memory_id
    assert service.repository.get(first.memory_id).status == "superseded"
    facts = service.repository.list_profile_facts(subject_user_id="student-1")
    assert [fact.value for fact in facts] == ["用户偏好简短回答"]


def test_reader_enforces_token_budget() -> None:
    service = _service()
    for index in range(8):
        service.confirm_profile_fact(
            actor={"user_id": "student-1"},
            profile_axis=f"custom_axis_{index}",
            value="用户偏好" + ("很长的说明" * 20) + str(index),
        )

    context = service.read_for_agent(
        actor={"user_id": "student-1"},
        conversation_id="conv-budget",
        course_id=None,
        task_id=None,
        query="",
        token_budget=40,
    )

    assert len(context.profile_facts) < 8
    assert "token_budget_truncated=true" in context.retrieval_notes
