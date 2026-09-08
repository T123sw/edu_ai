import json
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from app.database import Base
from app.artifact_revision.service import ArtifactRevisionService
from app.artifact_revision.adapters import validate, apply_edits
from core.config import Config  # Load dotenv before per-test isolated persistence settings.
from core.course_storage import CourseStorageManager


class Model:
    def __init__(self, output):
        self.output, self.prompts = output, []

    def invoke(self, prompt):
        self.prompts.append(prompt)
        supplied = json.loads(prompt[1]["content"])
        if "previous_proposal" in supplied and "edits" in self.output:
            output = {"confirm": True} if supplied["previous_proposal"] else {"proposal": {"scope": "案例", "changes": ["增加案例"], "reason": "帮助理解数组", "question": "按此修改可以吗？"}}
        else:
            output = self.output
        return SimpleNamespace(content=json.dumps(output, ensure_ascii=False))


@pytest.fixture(params=["json", "postgres"])
def manager(request, tmp_path, monkeypatch):
    monkeypatch.setenv("MATERIAL_PERSISTENCE_MODE", request.param)
    monkeypatch.setenv("KNOWLEDGE_PERSISTENCE_MODE", "json")
    monkeypatch.setenv("APP_STATE_PERSISTENCE_MODE", "json")
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    value = CourseStorageManager(str(tmp_path / "courses"))
    if request.param == "postgres":
        from app.persistence.postgres_material_repository import PostgresMaterialRepository
        engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(engine)
        repo = PostgresMaterialRepository(engine)
        monkeypatch.setattr(value, "_material_repository", lambda: repo)
    yield value
    if request.param == "postgres":
        engine.dispose()


def seed(manager, kind="report", content=None, artifact_id="one", **extra):
    data = {"title": "数组报告", "content": content if content is not None else "# 数组\n\n独特段落不变\n\n原始案例", **extra}
    assert manager.save_generated_material("course", kind, artifact_id, data, owner_user_id="teacher", visibility="private", scope_type="knowledge_point", scope_id="arrays")
    return {"artifact_id": artifact_id, "artifact_type": kind, "version_id": "v1", "source_course_id": "course"}


def run(service, ref=None, **kwargs):
    # Storage/patch tests start at execution of an approved plan. Discussion
    # and unapproved requests are covered through the public entry separately.
    return service.run(**{"owner_user_id": "teacher", "conversation_id": "conversation", "course_id": "course", "question": "增加两个实际案例", "operation_id": "op-1", "artifact_reference": ref, "execution_plan": {"scope": "案例", "changes": ["按已确认要求修改案例"], "reason": "教学示例"}, **kwargs})


def edit(path=None, before="原始案例", after="新案例"):
    return {"edits": [{"path": path or [], "before": before, "after": after}]}


def test_read_edit_persist_retry_history_restore_and_scope(manager):
    ref = seed(manager)
    model = Model(edit(after="原始案例\n案例一\n案例二"))
    service = ArtifactRevisionService(manager, model)
    result = run(service, ref, course_id="different", scope_id="linked-list")
    assert result["status"] == "completed", result
    assert result["artifact_reference"]["artifact_id"] == "one"
    assert result["artifact_reference"]["version_id"] == "v2"
    assert result["artifact"]["scope_id"] == "arrays"
    assert "独特段落不变" in result["artifact"]["content"]
    assert "独特段落不变" in model.prompts[0][1]["content"]
    assert run(service, ref, course_id="different")["artifact_reference"]["version_id"] == "v2"
    assert len(model.prompts) == 1
    old = service.read_version(owner_user_id="teacher", course_id="course", artifact_type="report", artifact_id="one", version=1)
    assert old["content"].endswith("原始案例")
    restored = service.restore(owner_user_id="teacher", course_id="course", artifact_type="report", artifact_id="one", version=1, base_version=2, operation_id="restore")
    assert restored["status"] == "completed", restored
    assert restored["artifact"]["material_version"] == 3
    assert restored["artifact"]["content"] == old["content"]


def test_conflict_and_duplicate_operation_binding(manager):
    ref = seed(manager)
    service = ArtifactRevisionService(manager, Model(edit()))
    assert run(service, ref)["status"] == "completed"
    assert run(service, ref, operation_id="op-2")["status"] == "conflict"
    assert run(service, ref, question="删除案例")["status"] == "conflict"
    assert manager.get_generated_material("course", "report", "one", owner_user_id="teacher")["version"] == 2


def test_permissions_publication_failure_and_no_model(manager):
    ref = seed(manager)
    service = ArtifactRevisionService(manager, Model({"edits": []}))
    assert run(service, ref, owner_user_id="other")["status"] == "failed"
    assert not service.llm.prompts
    assert run(service, ref)["status"] == "failed"
    assert run(ArtifactRevisionService(manager), ref)["status"] == "failed"
    assert manager.get_generated_material("course", "report", "one", owner_user_id="teacher")["version"] == 1
    seed(manager, artifact_id="published", published_from_material_id="one")
    assert run(service, {**ref, "artifact_id": "published"})["status"] == "failed"


def test_clarification_reads_original_and_continues_bound_operation(manager):
    ref = seed(manager)
    model = Model({"question": "第二部分需要简化表达还是增加案例？"})
    service = ArtifactRevisionService(manager, model)
    result = run(service, ref, question="第二部分不太好")
    assert result["status"] == "needs_clarification"
    assert "独特段落不变" in model.prompts[0][1]["content"]
    assert manager.get_generated_material("course", "report", "one", owner_user_id="teacher")["version"] == 1
    assert run(service, pending=result["pending"], owner_user_id="other")["status"] == "failed"
    model.output = edit(after="简单案例")
    completed = run(service, pending=result["pending"], question="简化表达", course_id="other-course")
    assert completed["status"] == "completed", completed
    assert "第二部分不太好" in model.prompts[-1][1]["content"]
    assert "简化表达" in model.prompts[-1][1]["content"]


def test_ambiguous_candidates_and_choose(manager):
    seed(manager)
    seed(manager, artifact_id="two")
    model = Model(edit())
    service = ArtifactRevisionService(manager, model)
    result = run(service, question="修改数组报告，简化案例")
    assert result["status"] == "needs_clarification", result
    assert len(result["candidates"]) == 2
    assert not model.prompts
    selected = result["candidates"][1]["artifact_id"]
    result = run(service, question="2", pending=result["pending"])
    assert result["status"] == "completed", result
    assert result["artifact_reference"]["artifact_id"] == selected


SAMPLES = [
    ("report", "原始内容", [], {}),
    ("blog", "原始内容 ![image](/media/one.png)", [], {}),
    ("lesson_plan", "# 教学目标\n原始内容", [], {}),
    ("quiz", {"questions": [{"id": "q1", "stem": "原始内容", "options": ["1", "2"], "answer": "A", "explanation": "因为是1"}]}, ["questions", 0, "stem"], {}),
    ("flashcard", {"cards": [{"front": "原始内容", "back": "背面"}]}, ["cards", 0, "front"], {}),
    ("graph", {"root": {"id": "root", "title": "原始内容", "children": [{"id": "child", "title": "保留"}]}}, ["root", "title"], {}),
    ("game", {"game_type": "drag_match", "template_id": "drag-match", "game_data": {"title": "原始内容", "pairs": [{"id": "a", "left": "1", "right": "一"}, {"id": "b", "left": "2", "right": "二"}]}}, ["game_data", "title"], {}),
    ("classroom", None, ["stage", "name"], {"stage": {"id": "one", "name": "原始内容"}, "scenes": [{"id": "s1", "content": {"type": "slide", "canvas": {"viewportRatio": 16/9, "elements": []}}, "actions": []}]}),
]


@pytest.mark.parametrize("kind,content,path,extra", SAMPLES)
def test_type_adapters_persist_valid_new_version(manager, kind, content, path, extra, tmp_path, monkeypatch):
    from app.chat.application.knowledge_base_direct_game_service_v2 import KnowledgeBaseDirectGameServiceV2
    original = KnowledgeBaseDirectGameServiceV2.__init__
    def init(self, **kwargs):
        original(self, **{**kwargs, "storage_root": tmp_path / "games"})
    monkeypatch.setattr(KnowledgeBaseDirectGameServiceV2, "__init__", init)
    ref = seed(manager, kind, content, **extra)
    service = ArtifactRevisionService(manager, Model(edit(path, "原始内容", "改进内容")))
    result = run(service, ref)
    assert result["status"] == "completed", result
    assert result["artifact"]["material_version"] == 2
    if kind == "quiz":
        assert result["artifact"]["questions"][0]["answer"] == "A"
    if kind == "classroom":
        assert result["artifact"]["stage"]["id"] == "one"
    if kind == "game":
        assert result["artifact"]["content"]["html_url"]
        assert "改进内容" in next((tmp_path / "games").rglob("index.html")).read_text()


def test_outline_and_structured_lesson(manager):
    for kind, payload, path in [
        ("report_outline", {"outline": [{"chapter_title": "原始标题", "chapter_goal": "保留"}]}, [0, "chapter_title"]),
        ("lesson_plan", {"plan": {"title": "原始标题", "objectives": ["目标"], "process": [{"step": "步骤", "content": "讲解"}]}}, ["title"]),
    ]:
        stored_kind = "report" if kind == "report_outline" else kind
        ref = seed(manager, stored_kind, artifact_id=kind, **payload)
        if kind == "lesson_plan":
            manager.update_generated_material_metadata("course", stored_kind, kind, {"content": None})
            ref["version_id"] = "v1"
        ref["artifact_type"] = kind
        service = ArtifactRevisionService(manager, Model(edit(path, "原始标题", "新版标题")))
        assert run(service, ref)["status"] == "completed"


@pytest.mark.parametrize("kind,content", [
    ("quiz", {"questions": [{"stem": "题目", "answer": "C", "explanation": "错误", "options": ["1", "2"]}]}),
    ("flashcard", {"cards": [{"front": "正面"}]}),
    ("graph", {"root": {"id": "r", "title": "r", "children": [{"id": "r", "title": "duplicate"}]}}),
    ("classroom", {"stage": {"id": "one"}, "scenes": [{"id": "s", "content": {"type": "slide", "canvas": {}}, "actions": []}]}),
])
def test_reject_invalid_structure(kind, content):
    with pytest.raises(ValueError):
        validate(kind, content)


def test_exact_patch_rejects_ambiguous_and_missing_source():
    with pytest.raises(ValueError):
        apply_edits("重复 重复", [{"path": [], "before": "重复", "after": "改"}])
    with pytest.raises(ValueError):
        apply_edits({"a": "文本"}, [{"path": ["missing"], "before": "文本", "after": "改"}])


def test_save_failure_preserves_old_material(manager, monkeypatch):
    ref = seed(manager)
    service = ArtifactRevisionService(manager, Model(edit()))
    def fail(*args, **kwargs):
        raise OSError("test disk failure")
    monkeypatch.setattr(service.storage, "_save_database", fail)
    monkeypatch.setattr(manager, "_persist_material_manifest", fail)
    assert run(service, ref)["status"] == "failed"
    assert manager.get_generated_material("course", "report", "one", owner_user_id="teacher")["version"] == 1


def test_concurrent_change_during_model_call(manager):
    ref = seed(manager)
    service = ArtifactRevisionService(manager)
    def invoke(prompt):
        manager.update_generated_material_metadata("course", "report", "one", {"content": "并发编辑"})
        return SimpleNamespace(content=json.dumps(edit()))
    service.llm = SimpleNamespace(invoke=invoke)
    assert run(service, ref)["status"] == "conflict"
    assert manager.get_generated_material("course", "report", "one", owner_user_id="teacher")["content"] == "并发编辑"


def test_actual_generated_lesson_payload(manager):
    from app.chat.application.lesson_plan_service_v2 import _fallback_content
    payload = _fallback_content(outline=[{"chapter_title": "新授", "chapter_goal": "学习数组"}], slots={"topic": "数组", "objective": "掌握数组"}, preparation={})
    ref = seed(manager, "lesson_plan", payload)
    result = run(ArtifactRevisionService(manager, Model(edit(["objectives", 0], "掌握数组", "理解数组并完成例题"))), ref)
    assert result["status"] == "completed", result
    assert result["artifact"]["content"]["process"] == payload["process"]


def test_last_array_report_does_not_select_newer_linked_list(manager):
    seed(manager, artifact_id="arrays", created_at="2026-09-01T00:00:00")
    seed(manager, artifact_id="linked-list", title="链表报告", created_at="2026-09-02T00:00:00")
    result = run(ArtifactRevisionService(manager, Model(edit())), question="将上次生成的数组报告修改一下，增加案例")
    assert result["status"] == "needs_clarification", result
    assert [r["artifact_id"] for r in result["candidates"]] == ["arrays"]


def test_published_snapshot_and_source_links_unchanged(manager):
    ref = seed(manager, published_material_id="published", published_version=1)
    manager.save_published_material_manifest("course", "report", "published", {"content": "发布版本内容", "published_from_material_id": "one", "published_from_version": 1})
    published = manager.get_stored_generated_material("course", "report", "published")
    result = run(ArtifactRevisionService(manager, Model(edit())), ref)
    assert result["status"] == "completed"
    assert result["artifact"]["published_version"] == 1
    after = manager.get_stored_generated_material("course", "report", "published")
    assert after == published


def test_insert_and_delete_structured_items_preserves_others():
    source = {"cards": [{"front": "原卡", "back": "原答案"}]}
    inserted = apply_edits(source, [{"op": "insert", "path": ["cards", 1], "before": None, "after": {"front": "新卡", "back": "新答案"}}])
    validate("flashcard", inserted)
    assert inserted["cards"][0] == source["cards"][0]
    restored = apply_edits(inserted, [{"op": "delete", "path": ["cards", 1], "before": inserted["cards"][1], "after": None}])
    assert restored == source


def test_model_invalid_path_repair_before_only_one_save(manager):
    ref = seed(manager, "flashcard", {"cards": [{"front": "原文", "back": "保留"}]})
    outputs = iter([edit(["source", "cards", 0, "front"], "原文", "新文"), edit(["cards", 0, "front"], "原文", "新文")])
    model = SimpleNamespace(invoke=lambda prompt: SimpleNamespace(content=json.dumps(next(outputs))))
    result = run(ArtifactRevisionService(manager, model), ref)
    assert result["status"] == "completed"
    assert result["artifact"]["material_version"] == 2


@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("button", [False, True])
def test_shared_reply_entry_reads_and_saves_for_both_modes(manager, stream, button):
    from app.chat.application.reply_service_v2 import ReplyServiceV2
    from app.chat.persistence.conversation_store_adapter import ConversationStoreAdapter
    from tests.chat.test_reply_service_v2_artifact_reference import DummyStorage
    ref = seed(manager)
    storage = DummyStorage()
    service = ReplyServiceV2(
        artifact_revision_service=ArtifactRevisionService(manager, Model(edit())),
        conversation_store=ConversationStoreAdapter(storage=storage),
        course_storage_manager=manager,
    )
    payload = SimpleNamespace(question="将上次生成的数组报告修改一下，增加案例", conversation_id="conversation", owner="teacher", course_id="course", model_id=None, artifact_id=None, action_hint=None, allow_rag=False, allow_web=False, selected_doc_ids=[], artifact_reference=ref if button else None)
    if stream:
        events = list(service.reply_stream(payload))
        assert [e["type"] for e in events] == ["result", "done"]
        result = events[0]["payload"]
    else:
        result = service.reply(payload)
    if not button:
        assert result["artifact_revision"]["status"] == "needs_clarification", result
        payload.question = "1"
        result = list(service.reply_stream(payload))[0]["payload"] if stream else service.reply(payload)
    assert result["artifact_revision"]["status"] == "needs_clarification", result
    payload.question = "同意这个方案，开始修改"
    result = list(service.reply_stream(payload))[0]["payload"] if stream else service.reply(payload)
    assert result["artifact_revision"]["status"] == "completed", result
    assert result["artifacts"][0]["version_id"] == "v2"
    assert manager.get_generated_material("course", "report", "one", owner_user_id="teacher")["version"] == 2


def test_classroom_changed_speech_does_not_play_old_audio(manager):
    ref = seed(manager, "classroom", stage={"id": "one", "name": "课堂"}, scenes=[{"id": "s", "content": {"type": "slide", "canvas": {"viewportRatio": 16/9, "elements": []}}, "actions": [{"id": "a", "type": "speech", "text": "原讲解", "audioUrl": "/old.wav", "audioId": "old"}]}])
    result = run(ArtifactRevisionService(manager, Model(edit(["scenes", 0, "actions", 0, "text"], "原讲解", "新讲解"))), ref)
    assert result["status"] == "completed", result
    action = result["artifact"]["scenes"][0]["actions"][0]
    assert "audioUrl" not in action and "audioId" not in action
    old = ArtifactRevisionService(manager).read_version(owner_user_id="teacher", course_id="course", artifact_type="classroom", artifact_id="one", version=1)
    assert old["scenes"][0]["actions"][0]["audioUrl"] == "/old.wav"


def _process_save(root, barrier, queue, operation_id):
    from app.artifact_revision.storage import RevisionStorage, RevisionConflict
    storage = RevisionStorage(CourseStorageManager(root))
    source = storage.get("course", "report", "one", "teacher")
    barrier.wait(timeout=10)
    try:
        result = storage.save(source, {"content": operation_id}, owner="teacher", operation_id=operation_id, fingerprint=operation_id, summary="修改", changes=[])
        queue.put(("completed", result["version"]))
    except RevisionConflict:
        queue.put(("conflict", None))


def test_json_separate_processes_do_not_overwrite(tmp_path, monkeypatch):
    import multiprocessing
    if "fork" not in multiprocessing.get_all_start_methods():
        pytest.skip("fork-specific process contention test")
    monkeypatch.setenv("MATERIAL_PERSISTENCE_MODE", "json")
    manager = CourseStorageManager(str(tmp_path))
    seed(manager)
    context = multiprocessing.get_context("fork")
    barrier, queue = context.Barrier(2), context.Queue()
    workers = [context.Process(target=_process_save, args=(str(tmp_path), barrier, queue, f"op-{i}")) for i in range(2)]
    for worker in workers:
        worker.start()
    try:
        outcomes = [queue.get(timeout=15) for _ in workers]
        assert sorted(o[0] for o in outcomes) == ["completed", "conflict"]
        for worker in workers:
            worker.join(timeout=5)
            assert worker.exitcode == 0
        assert manager.get_generated_material("course", "report", "one", owner_user_id="teacher")["version"] == 2
    finally:
        for worker in workers:
            if worker.is_alive():
                worker.terminate()
                worker.join()


@pytest.mark.parametrize("kind,data", [
    ("memory_flip", {"title": "记忆", "matches": [{"pair_id": "a", "card_a": "一", "card_b": "1"}, {"pair_id": "b", "card_a": "二", "card_b": "2"}]}),
    ("category_sort", {"title": "分类", "categories": [{"id": "a", "name": "奇"}, {"id": "b", "name": "偶"}], "items": [{"id": "i1", "text": "1", "categoryId": "a"}, {"id": "i2", "text": "2", "categoryId": "b"}, {"id": "i3", "text": "3", "categoryId": "a"}]}),
])
def test_other_game_template_validation(kind, data):
    validate("game", {"game_type": kind, "game_data": data})


def test_legacy_server_file_is_read_and_retained(manager):
    assert manager.save_generated_material("course", "report", "one", {"title": "旧报告", "file_extension": ".md"}, file_data="独特段落\n原始案例".encode(), owner_user_id="teacher", visibility="private")
    ref = {"artifact_id": "one", "artifact_type": "report", "version_id": "v1", "source_course_id": "course"}
    result = run(ArtifactRevisionService(manager, Model(edit())), ref)
    assert result["status"] == "completed", result
    assert result["artifact"]["content"] == "独特段落\n新案例"
    assert result["artifact"]["file_path"] is None
    old = ArtifactRevisionService(manager).read_version(owner_user_id="teacher", course_id="course", artifact_type="report", artifact_id="one", version=1)
    assert (manager.get_course_dir("course") / old["file_path"]).read_text() == "独特段落\n原始案例"


def test_skill_read_answer_does_not_create_version(manager):
    ref = seed(manager)
    model = Model({'answer': '这份资料介绍数组，包含独特段落和原始案例。'})
    result = run(ArtifactRevisionService(manager, model), ref, question='这个文档写的什么')
    assert result['status'] == 'answered'
    assert result['artifact_reference']['version_id'] == 'v1'
    assert 'artifact' not in result and 'pending' not in result
    supplied = json.loads(model.prompts[0][1]['content'])
    assert supplied['source'] == '# 数组\n\n独特段落不变\n\n原始案例'
    assert supplied['current_question'] == '这个文档写的什么'
    assert supplied['reference']['artifact_id'] == 'one'
    assert manager.get_generated_material('course', 'report', 'one', owner_user_id='teacher')['version'] == 1


def test_skill_read_interlude_preserves_original_pending(manager):
    ref = seed(manager)
    model = Model({'question': '第二部分需要简化还是增加案例？'})
    service = ArtifactRevisionService(manager, model)
    pending = run(service, ref, question='第二部分不太好')['pending']
    model.output = {'answer': '第二部分是原始案例。'}
    answer = run(service, pending=pending, question='先说这个文档写的什么')
    assert answer['status'] == 'answered'
    assert answer['pending'] == pending
    model.output = edit()
    revised = run(service, pending=answer['pending'], question='增加两个实际案例')
    assert revised['status'] == 'completed'
    assert revised['artifact']['material_version'] == 2
    assert '先说这个文档写的什么' not in json.loads(model.prompts[-1][1]['content'])['instruction']


@pytest.mark.parametrize('output', [
    {'question': '具体追问'}, {'answer': ''},
    {'answer': '我来解释', 'edits': [{'path': [], 'before': '原始案例', 'after': '替换'}]},
])
def test_skill_invalid_or_mixed_action_cannot_write(manager, output):
    ref = seed(manager)
    model = Model(output)
    result = run(ArtifactRevisionService(manager, model), ref)
    assert result['status'] == 'failed'
    assert len(model.prompts) == 2
    assert manager.get_generated_material('course', 'report', 'one', owner_user_id='teacher')['version'] == 1


def test_missing_revision_skill_fails_without_model_or_write(manager, tmp_path):
    from app.chat.skill_manager import SkillManager
    ref = seed(manager)
    model = Model(edit())
    service = ArtifactRevisionService(manager, model, skill_manager=SkillManager(skills_dir=tmp_path / 'missing'))
    result = run(service, ref)
    assert result['status'] == 'failed'
    assert '技能未加载' in result['message']
    assert model.prompts == []
    assert manager.get_generated_material('course', 'report', 'one', owner_user_id='teacher')['version'] == 1


def test_named_single_material_requires_confirmation_then_edits(manager):
    seed(manager)
    model = Model(edit())
    service = ArtifactRevisionService(manager, model)
    result = run(service, question="帮我修改数组报告，简化案例")
    assert result["status"] == "needs_clarification"
    assert len(result["candidates"]) == 1
    assert not model.prompts
    result = run(service, question="1", pending=result["pending"])
    assert result["status"] == "completed"


def test_explicit_reference_hash_reads_without_target_confirmation(manager):
    from app.artifact_revision.service import reference
    seed(manager)
    material = manager.get_generated_material("course", "report", "one", owner_user_id="teacher")
    ref = reference(material)
    assert ref["content_hash"]
    model = Model({"answer": "文档包含独特段落和原始案例。"})
    service = ArtifactRevisionService(manager, model)
    result = run(service, ref, question="《数组报告》这个文档写了什么")
    assert result["status"] == "answered", result
    assert result["artifact_reference"]["content_hash"] == ref["content_hash"]
    assert manager.get_generated_material("course", "report", "one", owner_user_id="teacher")["version"] == 1
    mismatch = run(service, {**ref, "content_hash": "wrong"}, question="《数组报告》解释案例", operation_id="op-2")
    assert mismatch["status"] == "conflict", mismatch
    assert len(model.prompts) == 1
