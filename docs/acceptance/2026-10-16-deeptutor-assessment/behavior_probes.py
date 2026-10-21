"""Offline probes of unmodified DeepTutor; run with upstream on PYTHONPATH.

Model/network boundaries are mocked. These reproduce control flow and prompt
assembly only, not generation quality. No application data or credentials used.
"""
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from deeptutor.agents.question.pipeline import QuestionPipeline, QuizPair, QuizPlan, QuizTemplate
from deeptutor.core.context import UnifiedContext
from deeptutor.runtime.stream_bus import StreamBus
from deeptutor.services.llm.config import LLMConfig


async def main():
    sentinel = "USER_REQUIREMENT_SENTINEL_UseLomutoPartition"
    context = UnifiedContext(user_message=sentinel, session_id="offline-assessment")
    template = QuizTemplate(question_id="q_1", topic="quicksort", question_type="short_answer",
                            difficulty="medium", source="mimic", reference_question="Explain quicksort.")
    with patch("deeptutor.agents.question.pipeline.get_llm_config",
               return_value=LLMConfig(model="offline-model", api_key="not-a-real-key")):
        pipeline = QuestionPipeline(language="zh")
    captured = {}

    async def fake_loop(**kwargs):
        captured["messages"] = kwargs["initial_messages"]
        return SimpleNamespace(final_text=json.dumps({
            "question_type": "short_answer", "question": "Explain quicksort partitioning.",
            "correct_answer": "Partition then recurse.", "explanation": "Divide and conquer."
        }))

    with patch.object(pipeline, "_tool_list_text", return_value="- none"), \
         patch.object(pipeline, "_use_native_tools", return_value=False), \
         patch("deeptutor.agents.question.pipeline.run_agentic_loop", side_effect=fake_loop):
        pair = await pipeline._quiz_one(template=template, question_number=1, total_questions=1,
            exploration_trace="", plan=QuizPlan(analysis="", templates=[template]), previous_pairs=[],
            image_attachments=[], context=context, stream=StreamBus(), client=object())
    messages = json.dumps(captured["messages"], ensure_ascii=False)
    assert sentinel not in messages
    assert template.reference_question in messages

    bus = StreamBus()
    with patch.object(pipeline, "_prepare_pageindex_tools", new=AsyncMock()), \
         patch.object(pipeline, "_explore", new=AsyncMock(return_value=("preface", "trace"))) as explore, \
         patch.object(pipeline, "_plan", new=AsyncMock(return_value=QuizPlan(analysis="", templates=[template]))), \
         patch.object(pipeline, "_quiz_one", new=AsyncMock(return_value=pair)), \
         patch("deeptutor.agents.question.pipeline.build_openai_client", return_value=object()):
        payload = await pipeline.run(context=context, user_message=sentinel, num_questions=1,
                                     templates_override=[], stream=bus)
        assert explore.await_count == 1
        assert payload["mode"] == "custom"
    await bus.close()
    events = [event async for event in bus.subscribe()]
    emitted = [event for event in events if event.metadata.get("call_kind") == "quiz_question_emitted"]
    assert emitted[0].metadata["qa_pair"]["correct_answer"] == pair.correct_answer
    print(json.dumps({
        "upstream_commit": "6cf793bd868ba5ecbe64722936d4be8fab5a01df",
        "real_model_calls": 0,
        "mimic_quiz_prompt": {"reference_present": True, "user_requirement_present": False},
        "empty_templates_override": {"explore_calls": explore.await_count, "result_mode": payload["mode"]},
        "question_content_event_contains_correct_answer": True,
        "scope": "Offline control-flow and prompt probes; not end-to-end generation validation"
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
