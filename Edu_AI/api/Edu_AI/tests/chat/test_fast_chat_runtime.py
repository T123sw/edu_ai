from pathlib import Path
from types import SimpleNamespace

from app.chat.domain.capability_policy import CapabilityPolicy
from app.chat.domain.contracts import ChatRequestV2
from app.chat.runtime.fast_chat_runtime import FastChatRuntime


PNG_DATA_URL = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO6Z0ioAAAAASUVORK5CYII="
)


class DummyGateway:
    def __init__(self):
        self.call_count = 0
        self.last_messages = None

    def chat(self, messages, temperature=0.2, max_tokens=1200):
        self.call_count += 1
        self.last_messages = messages
        return "test reply"


class DummyRetriever:
    def __init__(self, result=None):
        self.calls = []
        self.result = result or {
            "ok": True,
            "payload": {
                "answer": "retrieved summary",
                "sources": [{"source": "doc-a", "content": "chunk text", "page": 1}],
            },
        }

    def __call__(self, *, query, top_k=5, selected_doc_ids=None, owner=None):
        self.calls.append(
            {
                "query": query,
                "top_k": top_k,
                "selected_doc_ids": list(selected_doc_ids or []),
                "owner": owner,
            }
        )
        return self.result


class StreamingGateway(DummyGateway):
    def stream_chat(self, messages, temperature=0.2, max_tokens=1200):
        self.call_count += 1
        self.last_messages = messages
        yield "hello"
        yield " world"


def test_fast_runtime_builds_direct_reply():
    runtime = FastChatRuntime(model_gateway=DummyGateway())

    result = runtime.run(request=ChatRequestV2(question="hello"), snapshot=None, decision=None)

    assert result["message"]["content"] == "test reply"
    assert result["action"]["name"] == "chat.reply"
    assert result["conversation"]["conversation_id"] == ""


def test_fast_runtime_uses_recent_context_without_tools():
    gateway = DummyGateway()
    snapshot = SimpleNamespace(
        recent_messages=[{"role": "user", "content": "previous context"}],
        active_artifact=None,
    )
    runtime = FastChatRuntime(model_gateway=gateway)

    result = runtime.run(request=ChatRequestV2(question="continue"), snapshot=snapshot, decision=None)

    assert gateway.call_count == 1
    assert result["trace"]["path"] == "fast"
    assert result["sources"] == []


def test_fast_runtime_preserves_request_conversation_id():
    runtime = FastChatRuntime(model_gateway=DummyGateway())

    result = runtime.run(
        request=ChatRequestV2(question="hello", conversation_id="conv-fast"),
        snapshot=None,
        decision=None,
    )

    assert result["conversation"]["conversation_id"] == "conv-fast"


def test_fast_runtime_uses_multimodal_user_blocks_when_input_images_exist():
    gateway = DummyGateway()
    runtime = FastChatRuntime(model_gateway=gateway)
    image_path = Path(__file__).with_name("_runtime_multimodal_test_image.png")
    image_path.write_bytes(
        bytes.fromhex(
            "89504E470D0A1A0A0000000D49484452000000010000000108060000001F15C4890000000D49444154789C6360000002000154A24F5D0000000049454E44AE426082"
        )
    )
    try:
        request = SimpleNamespace(
            question="请描述这张图",
            conversation_id="conv-image",
            owner="teacher-a",
            input_images=[
                {
                    "image_id": "img-1",
                    "file_name": "diagram.png",
                    "mime_type": "image/png",
                    "storage_path": str(image_path),
                    "relative_path": "chat_images/diagram.png",
                    "image_url": "/api/chat/v2/images/chat_images/diagram.png",
                    "source": "paste",
                }
            ],
            capability=CapabilityPolicy(),
        )

        runtime.run(request=request, snapshot=None, decision=None)

        user_message = gateway.last_messages[-1]
        assert isinstance(user_message["content"], list)
        assert user_message["content"][0]["type"] == "text"
        assert user_message["content"][1]["type"] == "image_url"
        assert user_message["content"][1]["image_url"]["url"].startswith("data:image/png;base64,")
    finally:
        image_path.unlink(missing_ok=True)


def test_fast_runtime_replays_recent_user_images_in_follow_up_turns():
    gateway = DummyGateway()
    runtime = FastChatRuntime(model_gateway=gateway)
    image_path = Path(__file__).with_name("_runtime_history_multimodal_test_image.png")
    image_path.write_bytes(
        bytes.fromhex(
            "89504E470D0A1A0A0000000D49484452000000010000000108060000001F15C4890000000D49444154789C6360000002000154A24F5D0000000049454E44AE426082"
        )
    )
    try:
        snapshot = SimpleNamespace(
            recent_messages=[
                {
                    "role": "user",
                    "content": "这是刚才那张图",
                    "input_images": [
                        {
                            "image_id": "img-history-1",
                            "file_name": "history.png",
                            "mime_type": "image/png",
                            "storage_path": str(image_path),
                            "relative_path": "chat_images/history.png",
                            "image_url": "/api/chat/v2/images?path=chat_images%2Fhistory.png",
                            "source": "upload",
                        }
                    ],
                }
            ],
            active_artifact=None,
        )

        runtime.run(request=ChatRequestV2(question="继续讨论", conversation_id="conv-history"), snapshot=snapshot, decision=None)

        replayed_user_message = gateway.last_messages[1]
        assert replayed_user_message["role"] == "user"
        assert isinstance(replayed_user_message["content"], list)
        assert replayed_user_message["content"][0]["type"] == "text"
        assert replayed_user_message["content"][1]["type"] == "image_url"
        assert replayed_user_message["content"][1]["image_url"]["url"].startswith("data:image/png;base64,")
    finally:
        image_path.unlink(missing_ok=True)


def test_fast_runtime_uses_multimodal_user_blocks_when_input_videos_exist():
    gateway = DummyGateway()
    runtime = FastChatRuntime(model_gateway=gateway)
    video_path = Path(__file__).with_name("_runtime_multimodal_test_video.mp4")
    video_path.write_bytes(b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom")
    try:
        request = SimpleNamespace(
            question="请分析这个视频",
            conversation_id="conv-video",
            owner="teacher-a",
            input_videos=[
                {
                    "video_id": "vid-1",
                    "file_name": "clip.mp4",
                    "mime_type": "video/mp4",
                    "storage_path": str(video_path),
                    "relative_path": "chat_videos/clip.mp4",
                    "video_url": "/api/chat/v2/videos?path=chat_videos%2Fclip.mp4",
                    "source": "upload",
                }
            ],
            capability=CapabilityPolicy(),
        )
        runtime._extract_video_frame_data_urls = lambda *_args, **_kwargs: [PNG_DATA_URL, PNG_DATA_URL]

        runtime.run(request=request, snapshot=None, decision=None)

        user_message = gateway.last_messages[-1]
        assert isinstance(user_message["content"], list)
        assert user_message["content"][0]["type"] == "text"
        assert [block["type"] for block in user_message["content"][1:]] == ["image_url", "image_url"]
        assert all(
            block["image_url"]["url"].startswith("data:image/png;base64,")
            for block in user_message["content"][1:]
        )
    finally:
        video_path.unlink(missing_ok=True)


def test_fast_runtime_replays_recent_user_videos_in_follow_up_turns():
    gateway = DummyGateway()
    runtime = FastChatRuntime(model_gateway=gateway)
    video_path = Path(__file__).with_name("_runtime_history_multimodal_test_video.mp4")
    video_path.write_bytes(b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom")
    try:
        snapshot = SimpleNamespace(
            recent_messages=[
                {
                    "role": "user",
                    "content": "这是刚才那个视频",
                    "input_videos": [
                        {
                            "video_id": "vid-history-1",
                            "file_name": "history.mp4",
                            "mime_type": "video/mp4",
                            "storage_path": str(video_path),
                            "relative_path": "chat_videos/history.mp4",
                            "video_url": "/api/chat/v2/videos?path=chat_videos%2Fhistory.mp4",
                            "source": "upload",
                        }
                    ],
                }
            ],
            active_artifact=None,
        )
        runtime._extract_video_frame_data_urls = lambda *_args, **_kwargs: [PNG_DATA_URL]

        runtime.run(request=ChatRequestV2(question="继续讨论", conversation_id="conv-history"), snapshot=snapshot, decision=None)

        replayed_user_message = gateway.last_messages[1]
        assert replayed_user_message["role"] == "user"
        assert isinstance(replayed_user_message["content"], list)
        assert replayed_user_message["content"][0]["type"] == "text"
        assert replayed_user_message["content"][1]["type"] == "image_url"
        assert replayed_user_message["content"][1]["image_url"]["url"].startswith("data:image/png;base64,")
    finally:
        video_path.unlink(missing_ok=True)


def test_fast_runtime_uses_rag_retriever_when_allowed():
    gateway = DummyGateway()
    retriever = DummyRetriever()
    runtime = FastChatRuntime(model_gateway=gateway, rag_retriever=retriever)
    request = ChatRequestV2(
        question="请根据知识库总结关羽生平",
        conversation_id="conv-rag",
        owner="teacher-a",
        capability=CapabilityPolicy(allow_rag=True, selected_doc_ids=["doc-1"]),
    )

    result = runtime.run(request=request, snapshot=None, decision=None)

    assert retriever.calls == [
        {
            "query": "请根据知识库总结关羽生平",
            "top_k": 5,
            "selected_doc_ids": ["doc-1"],
            "owner": "teacher-a",
        }
    ]
    assert result["sources"][0]["source"] == "doc-a"
    assert "retrieved summary" in gateway.last_messages[-1]["content"]


def test_fast_runtime_run_stream_emits_metadata_delta_and_result_in_order():
    gateway = StreamingGateway()
    retriever = DummyRetriever()
    runtime = FastChatRuntime(model_gateway=gateway, rag_retriever=retriever)
    request = ChatRequestV2(
        question="use rag",
        conversation_id="conv-stream",
        owner="teacher-a",
        capability=CapabilityPolicy(allow_rag=True, selected_doc_ids=["doc-1"]),
    )

    events = list(runtime.run_stream(request=request, snapshot=None, decision=None))

    assert [event["type"] for event in events] == ["metadata", "delta", "delta", "result"]
    assert events[0]["payload"]["conversation_id"] == "conv-stream"
    assert events[0]["payload"]["sources"][0]["source"] == "doc-a"
    assert events[1]["payload"]["content"] == "hello"
    assert events[2]["payload"]["content"] == " world"
    assert events[3]["payload"]["message"]["content"] == "hello world"
    assert "retrieved summary" in gateway.last_messages[-1]["content"]


def test_fast_runtime_injects_rag_image_sources_into_multimodal_prompt(monkeypatch):
    gateway = DummyGateway()
    image_path = Path(__file__).with_name("_runtime_rag_image_source.png")
    image_path.write_bytes(
        bytes.fromhex(
            "89504E470D0A1A0A0000000D49484452000000010000000108060000001F15C4890000000D49444154789C6360000002000154A24F5D0000000049454E44AE426082"
        )
    )
    storage_root = image_path.parent / "_runtime_rag_storage"
    target_path = storage_root / "images" / "teacher-a" / "rag.png"
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_bytes(image_path.read_bytes())

    retriever = DummyRetriever(
        {
            "ok": True,
            "payload": {
                "answer": "图片资料说明了人物关系",
                "sources": [
                    {
                        "source": "doc-image",
                        "content": "人物关系图",
                        "metadata": {
                            "modality": "image",
                            "image_url": "/api/rag/image?path=images%2Fteacher-a%2Frag.png",
                        },
                    }
                ],
            },
        }
    )
    monkeypatch.setattr("app.chat.runtime.fast_chat_runtime.Config.STORAGE_ROOT", storage_root)
    runtime = FastChatRuntime(model_gateway=gateway, rag_retriever=retriever)
    request = ChatRequestV2(
        question="请结合图片回答",
        conversation_id="conv-rag-image",
        owner="teacher-a",
        capability=CapabilityPolicy(allow_rag=True),
    )

    try:
        runtime.run(request=request, snapshot=None, decision=None)

        user_message = gateway.last_messages[-1]
        assert isinstance(user_message["content"], list)
        assert user_message["content"][0]["type"] == "text"
        assert user_message["content"][1]["type"] == "image_url"
        assert user_message["content"][1]["image_url"]["url"].startswith("data:image/png;base64,")
    finally:
        image_path.unlink(missing_ok=True)
        if storage_root.exists():
            for item in sorted(storage_root.rglob("*"), reverse=True):
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    item.rmdir()


def test_fast_runtime_skips_rag_when_not_allowed():
    gateway = DummyGateway()
    retriever = DummyRetriever()
    runtime = FastChatRuntime(model_gateway=gateway, rag_retriever=retriever)
    request = ChatRequestV2(
        question="hello",
        conversation_id="conv-fast",
        capability=CapabilityPolicy(allow_rag=False, selected_doc_ids=["doc-1"]),
    )

    result = runtime.run(request=request, snapshot=None, decision=None)

    assert retriever.calls == []
    assert result["sources"] == []


def test_fast_runtime_includes_video_sources_when_video_retriever_is_available():
    gateway = DummyGateway()
    video_retriever = DummyRetriever(
        {
            "ok": True,
            "payload": {
                "summary": "视频片段显示关羽的主要经历",
                "sources": [
                    {
                        "source": "关羽人物解析",
                        "content": "第 12 秒到 24 秒讲解了关羽的主要经历",
                        "metadata": {
                            "modality": "video",
                            "video_url": "/api/video/stream?rel_path=videos%2Fteacher-a%2Fclip.mp4",
                            "start_time": 12.0,
                            "end_time": 24.0,
                        },
                    }
                ],
            },
        }
    )
    runtime = FastChatRuntime(model_gateway=gateway, video_retriever=video_retriever)
    request = ChatRequestV2(
        question="根据视频总结关羽的经历",
        conversation_id="conv-video",
        owner="teacher-a",
        capability=CapabilityPolicy(allow_rag=True),
    )

    result = runtime.run(request=request, snapshot=None, decision=None)

    assert video_retriever.calls == [
        {
            "query": "根据视频总结关羽的经历",
            "top_k": 5,
            "selected_doc_ids": [],
            "owner": "teacher-a",
        }
    ]
    assert any(
        source.get("metadata", {}).get("modality") == "video"
        for source in result["sources"]
    )
    assert "视频片段显示关羽的主要经历" in gateway.last_messages[-1]["content"]


def test_fast_runtime_uses_web_retriever_when_allowed():
    gateway = DummyGateway()
    web_retriever = DummyRetriever(
        {
            "ok": True,
            "payload": {
                "summary": "web summary",
                "sources": [{"source": "https://example.com", "content": "web chunk", "page": 0}],
            },
        }
    )
    runtime = FastChatRuntime(model_gateway=gateway, web_retriever=web_retriever)
    request = ChatRequestV2(
        question="请联网总结关羽生平",
        conversation_id="conv-web",
        owner="teacher-a",
        capability=CapabilityPolicy(allow_web=True),
    )

    result = runtime.run(request=request, snapshot=None, decision=None)

    assert web_retriever.calls == [
        {
            "query": "请联网总结关羽生平",
            "top_k": 5,
            "selected_doc_ids": [],
            "owner": "teacher-a",
        }
    ]
    assert result["sources"][0]["source"] == "https://example.com"
    assert "web summary" in gateway.last_messages[-1]["content"]


def test_fast_runtime_instructs_model_to_use_live_web_results_when_available():
    gateway = DummyGateway()
    web_retriever = DummyRetriever(
        {
            "ok": True,
            "payload": {
                "summary": "web summary",
                "sources": [{"source": "https://example.com", "content": "web chunk", "page": 0}],
            },
        }
    )
    runtime = FastChatRuntime(model_gateway=gateway, web_retriever=web_retriever)
    request = ChatRequestV2(
        question="请联网总结关羽生平",
        conversation_id="conv-web",
        owner="teacher-a",
        capability=CapabilityPolicy(allow_web=True),
    )

    runtime.run(request=request, snapshot=None, decision=None)

    assert "你当前已经拿到了联网检索结果" in gateway.last_messages[0]["content"]


def test_fast_runtime_uses_teacher_style_system_prompt():
    gateway = DummyGateway()
    runtime = FastChatRuntime(model_gateway=gateway)

    runtime.run(request=ChatRequestV2(question="什么是牛顿第一定律"), snapshot=None, decision=None)

    system_prompt = gateway.last_messages[0]["content"]
    assert "你是一位专业、耐心、善于启发的学科教师" in system_prompt
    assert "先直接回答用户当前的问题" in system_prompt
    assert "提供2-3个自然延伸的学习方向" in system_prompt
    assert "只在适合继续引导时" in system_prompt


def test_fast_runtime_keeps_teacher_style_when_rag_context_exists():
    gateway = DummyGateway()
    retriever = DummyRetriever()
    runtime = FastChatRuntime(model_gateway=gateway, rag_retriever=retriever)
    request = ChatRequestV2(
        question="请根据知识库解释什么是光合作用",
        conversation_id="conv-rag",
        owner="teacher-a",
        capability=CapabilityPolicy(allow_rag=True, selected_doc_ids=["doc-1"]),
    )

    runtime.run(request=request, snapshot=None, decision=None)

    system_prompt = gateway.last_messages[0]["content"]
    assert "你是一位专业、耐心、善于启发的学科教师" in system_prompt
    assert "优先依据已经提供的检索信息作答" in system_prompt
    assert "不要忽略这些参考信息" in system_prompt


def test_fast_runtime_exposes_web_trace_details():
    gateway = DummyGateway()
    web_retriever = DummyRetriever(
        {
            "ok": True,
            "payload": {
                "summary": "web summary",
                "sources": [
                    {"source": "https://example.com/a", "content": "web chunk", "page": 0},
                    {"source": "https://example.com/b", "content": "web chunk", "page": 0},
                ],
                "trace": {
                    "web_links_count": 8,
                    "web_imported_count": 6,
                    "web_selected_doc_ids_count": 12,
                },
            },
        }
    )
    runtime = FastChatRuntime(model_gateway=gateway, web_retriever=web_retriever)
    request = ChatRequestV2(
        question="请联网总结关羽生平",
        conversation_id="conv-web",
        owner="teacher-a",
        capability=CapabilityPolicy(allow_web=True),
    )

    result = runtime.run(request=request, snapshot=None, decision=None)

    assert result["trace"]["web_used"] is True
    assert result["trace"]["web_links_count"] == 8
    assert result["trace"]["web_imported_count"] == 6
    assert result["trace"]["web_selected_doc_ids_count"] == 12
    assert result["trace"]["web_sources_count"] == 2


def test_fast_runtime_appends_artifact_context_block_before_user_question():
    gateway = DummyGateway()
    runtime = FastChatRuntime(model_gateway=gateway)
    request = ChatRequestV2(question="这份报告的核心观点是什么？", conversation_id="conv-artifact")

    runtime.run(
        request=request,
        snapshot=SimpleNamespace(recent_messages=[], active_artifact=None),
        decision=SimpleNamespace(action="chat.reply"),
        artifact_context={
            "artifact_type": "report",
            "title": "李白性格分析.md",
            "context_text": "## 摘要\n原摘要。\n\n## 结论\n原结论。",
        },
    )

    user_message = gateway.last_messages[-1]["content"]
    assert "Referenced artifact: 李白性格分析.md" in user_message
    assert "## 摘要" in user_message
    assert "User question: 这份报告的核心观点是什么？" in user_message
