import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from deeptutor.agents.question.pipeline import QuestionPipeline, QuizPlan, QuizTemplate
from deeptutor.core.context import UnifiedContext
from deeptutor.runtime.agentic import LabeledStepResult
from deeptutor.runtime.stream_bus import StreamBus
from deeptutor.services.llm.config import LLMConfig


@pytest.fixture
def pipeline(monkeypatch):
    monkeypatch.setattr("deeptutor.agents.question.pipeline.get_llm_config", lambda: LLMConfig(model="offline-model", api_key="fake"))
    instance = QuestionPipeline(language="zh")
    monkeypatch.setattr(instance, "_prepare_pageindex_tools", AsyncMock())
    monkeypatch.setattr("deeptutor.agents.question.pipeline.build_openai_client", lambda config: object())
    return instance


async def test_empty_exam_never_falls_back_to_custom(pipeline):
    with patch.object(pipeline, "_explore", new=AsyncMock()) as explore:
        with pytest.raises(ValueError, match="no templates"):
            await pipeline.run(context=UnifiedContext(), user_message="仿卷", num_questions=1, templates_override=[], stream=StreamBus())
        explore.assert_not_called()


async def test_user_requirements_reach_mimic_generation_and_format_repair(pipeline, monkeypatch):
    sentinel = "REQUIRE_LOMUTO_PARTITION_AND_NO_RECURSION"
    captured = []
    template = QuizTemplate(question_id="q1", topic="quicksort", question_type="short_answer", difficulty="medium",
                            source="mimic", reference_question="Explain one partition step")
    async def loop(**kwargs):
        captured.append(kwargs["initial_messages"])
        return SimpleNamespace(final_text='{"question":"Incomplete payload"}')
    async def repair(**kwargs):
        captured.append(kwargs["messages"])
        return LabeledStepResult(label="FINISH", text=json.dumps({"question": "Explain partition", "correct_answer": "Partition around pivot", "explanation": "One partition step"}))
    monkeypatch.setattr(pipeline, "_tool_list_text", lambda ctx: "- none")
    monkeypatch.setattr(pipeline, "_use_native_tools", lambda ctx: False)
    monkeypatch.setattr("deeptutor.agents.question.pipeline.run_agentic_loop", loop)
    monkeypatch.setattr(pipeline, "_run_labeled_step", repair)
    pair = await pipeline._quiz_one(template=template, question_number=1, total_questions=1,
        exploration_trace="", plan=QuizPlan(analysis="", templates=[template]), previous_pairs=[], image_attachments=[],
        context=UnifiedContext(user_message=sentinel), stream=StreamBus(), client=object())
    assert len(captured) == 2
    assert all(sentinel in json.dumps(messages) for messages in captured)
    assert template.reference_question in json.dumps(captured[0])
    assert not pair.metadata.get("issues")


async def test_full_fifteen_question_template_survives_without_count_limit(tmp_path):
    from deeptutor.agents.question.mimic_source import parse_exam_paper_to_templates
    from deeptutor.runtime.request_contracts import DeepQuestionRequestConfig
    config = DeepQuestionRequestConfig(mode="mimic", max_questions=0, num_questions=150)
    questions = [{"question_text": f"Question {i + 1}", "question_type": "choice" if i < 10 else "fill_in_blank", "difficulty": "medium"} for i in range(15)]
    (tmp_path / "paper_questions.json").write_text(json.dumps({"questions": questions}))
    templates, trace = await parse_exam_paper_to_templates(tmp_path, max_questions=config.max_questions, paper_mode="parsed", output_dir=tmp_path)
    assert [t.question_type for t in templates] == ["choice"] * 10 + ["fill_in_blank"] * 5
    assert trace["template_count"] == "15"


async def test_terminal_row_does_not_overtake_owner_done_event(tmp_path):
    from deeptutor.app.service import TurnApplicationService
    from deeptutor.runtime.coordination import MemoryCoordinator
    from deeptutor.services.session.sqlite_store import SQLiteSessionStore
    store = SQLiteSessionStore(tmp_path / "events.db")
    coordinator = MemoryCoordinator(lease_ttl_seconds=30)
    session = await store.ensure_session("test-session")
    lease = await coordinator.acquire_turn("test-turn", "scope", "worker-a")
    await store.begin_turn(session["id"], turn_id="test-turn", owner_id="worker-a", fencing_token=lease.fencing_token)
    await store.transition_turn("test-turn", "completed", expected_status="running", fencing_token=lease.fencing_token)
    service = TurnApplicationService(SimpleNamespace(get=lambda: store), SimpleNamespace(get=lambda store: None), coordinator)
    async def finish():
        await asyncio.sleep(0.05)
        await coordinator.publish_event("test-turn", {"type": "done", "metadata": {"status": "completed", "user_message_id": 42}})
        await coordinator.release_turn(lease)
    task = asyncio.create_task(finish())
    async def collect():
        return [event async for event in service.subscribe_turn("test-turn")]
    events = await asyncio.wait_for(collect(), timeout=2)
    await task
    assert events[-1]["metadata"]["user_message_id"] == 42
    assert not events[-1]["metadata"].get("synthesized")


async def test_completed_turn_drains_durable_result_after_partial_live_batch():
    from deeptutor.app.service import TurnApplicationService
    frames = [
        {"seq": 1, "type": "thinking", "metadata": {}},
        {"seq": 2, "type": "result", "metadata": {"summary": {"completed": 32}}},
        {"seq": 3, "type": "done", "metadata": {"status": "completed"}},
    ]
    store = SimpleNamespace(
        get_turn=AsyncMock(return_value={"status": "completed", "session_id": "s"}),
        # The initial replay was empty while the worker was still starting.
        get_events=AsyncMock(side_effect=[[], frames[1:]]),
    )
    coordinator = SimpleNamespace(
        read_events=AsyncMock(side_effect=[[frames[0]], []]),
        get_lease=AsyncMock(return_value=None),
    )
    service = TurnApplicationService(SimpleNamespace(get=lambda: store), SimpleNamespace(get=lambda _: None), coordinator)
    result = [event async for event in service.subscribe_turn("t")]
    assert result == frames
    assert store.get_events.await_args_list[-1].args == ("t", 1)
