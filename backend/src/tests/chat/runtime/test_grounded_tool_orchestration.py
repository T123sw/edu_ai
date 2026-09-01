from types import SimpleNamespace

from app.chat.runtime.agent_tools import ToolExecutionContext
from app.chat.runtime.nodes.executor import _build_mandatory_retrieval_calls


def test_executor_forces_enabled_rag_even_when_current_plan_step_omits_it():
    capability = SimpleNamespace(
        allow_rag=True,
        allow_web=False,
        selected_doc_ids=["doc-linked-list"],
    )
    ctx = ToolExecutionContext(capability=capability, max_steps=4)
    state = {
        "current_plan": {
            "subject": "链表如何实现",
            "steps": [
                {
                    "index": 1,
                    "internal_action": "answer_question",
                    "expected_tools": [],
                },
                {
                    "index": 2,
                    "internal_action": "retrieve_context",
                    "expected_tools": ["rag_search"],
                },
            ],
        },
        "plan_step_index": 0,
    }
    runtime = {
        "request": SimpleNamespace(question="链表如何实现"),
    }

    calls = _build_mandatory_retrieval_calls(state, runtime, ctx)

    assert calls == [
        {
            "id": "forced_rag_search_1",
            "name": "rag_search",
            "args": {"query": "链表如何实现", "top_k": 5},
        }
    ]
