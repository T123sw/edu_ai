from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.chat.domain.capability_policy import CapabilityPolicy
from app.chat.domain.contracts import ChatRequestV2
from app.chat.persistence.agent_run_store import AgentRunStore
from app.chat.runtime.react_agent import ReActAgent


class MemoryGraph:
    def __init__(self):
        self.values = {}
        self.captured_messages = []
        self.turn = 0

    def get_state(self, config):
        del config
        return SimpleNamespace(values=dict(self.values))

    def stream(self, initial_input, config, stream_mode):
        del config, stream_mode
        self.turn += 1
        self.captured_messages.append(list(initial_input["messages"]))
        contract = (
            {
                "intent": "generate_single",
                "topic": "快速排序",
                "resource_types": ["report"],
            }
            if self.turn == 1
            else {"intent": "qa", "topic": ""}
        )
        self.values = {**initial_input, "task_contract": contract}
        return iter(())

    def update_state(self, config, patch):
        del config
        self.values = {**self.values, **patch}


@pytest.mark.parametrize("replace_graph", [False, True])
def test_latest_agent_memory_is_restored_same_process_and_after_restart(
    tmp_path,
    replace_graph,
):
    store = AgentRunStore(tmp_path / "agent_runs.db")
    agent = ReActAgent(
        agent_gateway=SimpleNamespace(),
        fast_runtime=SimpleNamespace(),
        agent_run_store=store,
    )
    graph = MemoryGraph()
    agent._graph = graph
    snapshot = SimpleNamespace(
        recent_messages=[],
        learning_context={},
        capability=CapabilityPolicy(),
    )
    first_request = ChatRequestV2(
        question="生成快速排序报告",
        conversation_id="conv-memory",
        owner="teacher-1",
        course_id="course-1",
    )

    list(agent.run_stream(request=first_request, snapshot=snapshot))

    if replace_graph:
        graph = MemoryGraph()
        graph.turn = 1
        agent._graph = graph

    second_request = first_request.model_copy(update={"question": "继续完善"})
    list(agent.run_stream(request=second_request, snapshot=snapshot))
    second_prompt = "\n".join(
        str(message.get("content") or "")
        for message in graph.captured_messages[-1]
        if message.get("role") == "system"
    )

    assert "【Agent 持久任务记忆】" in second_prompt
    assert "快速排序" in second_prompt
