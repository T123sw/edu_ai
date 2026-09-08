"""Iterative preview is private conversation state; only approval saves it."""
import json
from types import SimpleNamespace

from app.artifact_revision.service import ArtifactRevisionService
from app.chat.domain.artifact_reference import ArtifactDraftAction
from tests.chat.test_artifact_revision import manager, seed


class Model:
    def __init__(self, *outputs):
        self.outputs = iter(outputs)
        self.inputs = []
    def invoke(self, prompt):
        self.inputs.append(json.loads(prompt[1]['content']))
        return SimpleNamespace(content=json.dumps(next(self.outputs), ensure_ascii=False))


def change(before, after):
    return {'edits': [{'path': [], 'before': before, 'after': after}], 'focus': '案例段落',
            'reason': '用具体操作替代笼统描述。', 'benefit': '便于初学者理解。'}


def turn(service, ref, question, pending=None, action=None, owner='teacher'):
    return service.run(owner_user_id=owner, conversation_id='conv', course_id='course',
                       question=question, operation_id='draft-op', artifact_reference=ref,
                       pending=pending, draft_action=action)


def action(result, operation='save', **kwargs):
    draft = result['draft']
    return ArtifactDraftAction(action=operation, draft_id=draft['draft_id'], revision=draft['revision'], **kwargs)


def test_iterate_read_and_save_exact_preview_with_original_copy(manager):
    ref = seed(manager)
    model = Model(change('原始案例', '第一个例子'), change('第一个例子', '更简洁的例子'), {'answer': '当前修改稿的例子更简洁。'})
    service = ArtifactRevisionService(manager, model)
    first = turn(service, ref, '加个例子')
    assert first['status'] == 'preview' and '尚未保存' in first['message']
    assert first['draft']['reason'] in first['message'] and first['draft']['benefit'] in first['message']
    second = turn(service, ref, '再简洁一点', first['pending'])
    assert second['draft']['revision'] == 2
    assert '第一个例子' in model.inputs[1]['source']
    colored = second['draft']['segments']
    assert any(s['kind'] == 'delete' and '原始案例' in s['text'] for s in colored)
    assert any(s['kind'] == 'insert' and '更简洁的例子' in s['text'] for s in colored)
    assert all('第一个例子' not in s['text'] for s in colored)
    assert any(s['kind'] == 'focus' for s in colored)
    assert manager.get_generated_material('course','report','one',owner_user_id='teacher')['version'] == 1
    read = turn(service, ref, '为什么这样修改？', second['pending'])
    assert read['pending'] == second['pending'] and read['draft'] == second['draft']
    # Simulate restart: draft is restored only from serialized server conversation state.
    restored = json.loads(json.dumps(read['pending']))
    fresh_service = ArtifactRevisionService(manager)
    saved = turn(fresh_service, ref, '保存当前修改稿', restored, action(second))
    assert saved['status'] == 'completed', saved
    assert saved['artifact']['version']['version_number'] == 1
    assert saved['artifact']['content'].endswith('更简洁的例子')
    assert fresh_service.read_version(owner_user_id='teacher',course_id='course',artifact_type='report',artifact_id='one',version=1)['content'].endswith('原始案例')
    new_id = saved['artifact_reference']['artifact_id']
    assert new_id != 'one'
    original = manager.get_generated_material('course', 'report', 'one', owner_user_id='teacher')
    assert original['version'] == 1 and original['content'].endswith('原始案例')
    copy = manager.get_generated_material('course', 'report', new_id, owner_user_id='teacher')
    assert copy['title'].endswith('（修改稿）')
    assert copy['revision']['source_material_id'] == 'one'
    listed = manager.list_generated_materials('course', aggregate=True, owner_user_id='teacher')
    assert {item['material_id'] for item in listed} == {'one', new_id}
    repeated = turn(fresh_service, ref, '保存当前修改稿', restored, action(second))
    assert repeated['artifact_reference']['artifact_id'] == new_id
    assert len(model.inputs) == 3


def test_discard_never_writes_and_stale_action_is_rejected(manager):
    ref = seed(manager)
    service = ArtifactRevisionService(manager, Model(change('原始案例', '例子一'), change('例子一', '例子二')))
    first = turn(service, ref, '增加例子')
    second = turn(service, ref, '换一个', first['pending'])
    stale = turn(service, ref, '保存', second['pending'], action(first))
    assert stale['status'] == 'conflict'
    other = turn(service, ref, '保存', second['pending'], action(second), owner='other')
    assert other['status'] == 'failed'
    discarded = turn(service, ref, '放弃', second['pending'], action(second, 'discard'))
    assert discarded['status'] == 'discarded' and not discarded.get('pending')
    assert manager.get_generated_material('course','report','one',owner_user_id='teacher')['version'] == 1


def test_first_turn_cannot_save_and_natural_confirmation_saves_existing_draft(manager):
    ref = seed(manager)
    bad = ArtifactRevisionService(manager, Model({'save': True}, {'save': True}))
    assert turn(bad, ref, '直接改完保存')['status'] == 'failed'
    service = ArtifactRevisionService(manager, Model(change('原始案例', '新例子'), {'save': True}))
    draft = turn(service, ref, '加个例子')
    saved = turn(service, ref, '可以，保存吧', draft['pending'])
    assert saved['status'] == 'completed' and saved['artifact']['content'].endswith('新例子')


def test_external_version_change_blocks_save(manager):
    ref = seed(manager)
    service = ArtifactRevisionService(manager, Model(change('原始案例', '新例子')))
    draft = turn(service, ref, '加个例子')
    original = service.storage.get('course','report','one','teacher')
    service.storage.save(original, {'content': '其他编辑者的新版本'}, owner='teacher', operation_id='external', fingerprint='external', summary='外部修改', changes=[])
    result = turn(service, ref, '保存', draft['pending'], action(draft))
    assert result['status'] == 'conflict'
    assert manager.get_generated_material('course','report','one',owner_user_id='teacher')['content'] == '其他编辑者的新版本'
    assert turn(service, ref, '放弃', draft['pending'], action(draft, 'discard'))['status'] == 'discarded'


def test_invalid_iteration_preserves_last_usable_preview(manager):
    ref = seed(manager)
    invalid = change('不存在的原文', '替换')
    service = ArtifactRevisionService(manager, Model(change('原始案例', '新例子'), invalid, invalid))
    first = turn(service, ref, '加个例子')
    failed = turn(service, ref, '再调整', first['pending'])
    assert failed['status'] == 'failed' and failed['draft'] == first['draft']
    assert manager.get_generated_material('course','report','one',owner_user_id='teacher')['version'] == 1


def test_critical_ambiguity_asks_before_preview(manager):
    ref = seed(manager)
    service = ArtifactRevisionService(manager, Model({'question': '你指的是插入还是删除一节？'}))
    result = turn(service, ref, '把那个部分重写')
    assert result['status'] == 'needs_clarification' and 'draft' not in result


def test_provider_failure_logs_status_without_leaking_details(manager, caplog):
    ref = seed(manager)
    class ProviderError(Exception): status_code = 402
    class Unavailable:
        def invoke(self, prompt): raise ProviderError('private provider details')
    result = turn(ArtifactRevisionService(manager, Unavailable()), ref, '增加例子')
    assert result['status'] == 'failed' and '暂时不可用' in result['message']
    assert 'status=402' in caplog.text and 'private provider details' not in caplog.text + result['message']


def test_save_button_contract_restores_pending_and_updates_history_reference(manager):
    from app.chat.application.reply_service_v2 import ReplyServiceV2
    from app.chat.persistence.conversation_store_adapter import ConversationStoreAdapter
    from tests.chat.test_reply_service_v2_artifact_reference import DummyStorage
    ref = seed(manager)
    storage = DummyStorage()
    service = ReplyServiceV2(conversation_store=ConversationStoreAdapter(storage=storage),
        artifact_revision_service=ArtifactRevisionService(manager, Model(change('原始案例', '按钮保存的例子'))), course_storage_manager=manager)
    payload = SimpleNamespace(owner='teacher', conversation_id='conv', course_id='course', question='增加例子', artifact_reference=ref)
    first = service.reply(payload)
    draft = first['artifact_revision']['draft']
    assert storage.get_state('conv')['latest_revision_outcome']['draft'] == draft
    # UI sends only draft identity/action, never replacement content.
    payload.question = '保存当前修改稿'
    payload.artifact_draft_action = {'action': 'save', 'draft_id': draft['draft_id'], 'revision': draft['revision']}
    second = service.reply(payload)
    assert second['artifact_revision']['status'] == 'completed'
    assert second['artifact_revision']['artifact']['content'].endswith('按钮保存的例子')
    assert storage.get_state('conv')['pending_operation'] is None
    assert storage.get_state('conv')['artifact_reference']['version_id'] == 'v1'
