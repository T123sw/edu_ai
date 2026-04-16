from types import SimpleNamespace

from app.chat.orchestrator.main_orchestrator import MainOrchestrator


class DummyContextBuilder:
    def build(self, request):
        return SimpleNamespace(workflow_state=None)


class DummyFastRuntime:
    def run_stream(self, *, request, snapshot, decision):
        yield {"type": "metadata", "payload": {"conversation_id": request.conversation_id}}
        yield {"type": "delta", "payload": {"content": "ok"}}
        yield {
            "type": "result",
            "payload": {
                "message": {"role": "assistant", "content": "ok"},
                "conversation": {"conversation_id": request.conversation_id},
                "action": {"name": "chat.reply"},
                "workflow": None,
                "artifacts": [],
                "sources": [],
                "trace": {"path": "fast"},
            },
        }


def test_main_orchestrator_dispatch_stream_uses_fast_runtime():
    orchestrator = MainOrchestrator(
        fast_runtime=DummyFastRuntime(),
        workflow_registry={},
        context_builder=DummyContextBuilder(),
    )

    events = list(
        orchestrator.dispatch_stream(
            SimpleNamespace(question="hello", conversation_id="conv-1", action_hint=None)
        )
    )

    assert [event["type"] for event in events] == ["metadata", "delta", "result"]
    assert events[-1]["payload"]["message"]["content"] == "ok"
