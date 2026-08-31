from sqlalchemy import create_engine

from app.chat.domain.contracts import ChatRequestV2
from app.chat.domain.route_decision import RouteDecision
from app.chat.memory.langmem_adapter import LangMemAdapter
from app.chat.memory.repository import SqlAlchemyMemoryRepository
from app.chat.memory.service import AgentMemoryService
from app.chat.memory.settings import AgentMemorySettings
from app.chat.orchestrator.context_builder import ContextBuilder
from app.chat.runtime.fast_chat_runtime import FastChatRuntime
from app.database import Base


class _Gateway:
    def __init__(self):
        self.messages = []

    def chat(self, messages):
        self.messages = messages
        return "这是使用生活化例子的解释。"


def test_memory_flows_from_prior_turn_into_real_chat_prompt() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    settings = AgentMemorySettings(
        enabled=True,
        langmem_enabled=False,
        embedding_enabled=False,
    )
    service = AgentMemoryService(
        repository=SqlAlchemyMemoryRepository(engine),
        settings=settings,
        langmem_adapter=LangMemAdapter(settings=settings),
    )
    service.persist_turn(
        actor={"user_id": "student-e2e", "role": "student"},
        conversation_id="conv-old",
        course_id="course-a",
        user_message="我更喜欢用生活中的例子来理解抽象概念",
        assistant_message="好的。",
        agent_state={},
        tool_events=[],
    )

    request = ChatRequestV2(
        question="请解释递归",
        actor_role="student",
        conversation_id=None,
        owner="student-e2e",
        course_id="course-a",
    )
    snapshot = ContextBuilder(memory_reader=service).build(request)
    gateway = _Gateway()
    runtime = FastChatRuntime(model_gateway=gateway)
    runtime.run(
        request=request,
        snapshot=snapshot,
        decision=RouteDecision.fast(action="chat.reply", reason="e2e"),
    )

    assert snapshot.agent_memory_context["profile_facts"]
    assert "生活" in gateway.messages[0]["content"]
    assert "不作为成绩或掌握度事实" in gateway.messages[0]["content"]
