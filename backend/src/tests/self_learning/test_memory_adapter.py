from types import SimpleNamespace
from datetime import datetime,timedelta,timezone
import pytest
from app.self_learning.memory_adapter import MemoryAdapter
from app.chat.memory.lifecycle import MemoryChanged
from tests.chat.memory.test_memory_lifecycle import repo,draft


def test_edit_and_delete_use_revision_and_suppress_old_history(repo):
    old = repo.upsert_memory(draft())
    adapter = MemoryAdapter(repo._engine)
    context = adapter.read('alice', None)
    revision = context['preferences']['response_detail']['revision']
    updated = adapter.update_preference('alice', old.memory_id, '详细解释', revision)
    with pytest.raises(MemoryChanged): adapter.update_preference('alice', old.memory_id, '覆盖新值', revision)
    with pytest.raises(MemoryChanged): adapter.validate('alice', context)
    assert not adapter.permits_history('alice', SimpleNamespace(content='我说过讲解简洁', raw_payload={}))
    value = adapter.read('alice', None)['preferences']['response_detail']
    assert value['value'] == '详细解释'
    with pytest.raises(PermissionError): adapter.update_preference('bob', updated.memory_id, '越权', value['revision'])
    assert adapter.delete_preference('alice', updated.memory_id, value['revision'])
    assert adapter.read('alice', None)['preferences'] == {}


def test_expired_preference_is_not_effective(repo):
    repo.upsert_memory(draft(expires_at=datetime.now(timezone.utc)-timedelta(seconds=1)))
    assert MemoryAdapter(repo._engine).read('alice', None)['preferences'] == {}


def test_old_answer_dependency_is_not_injected_after_delete(repo):
    old = repo.upsert_memory(draft())
    adapter = MemoryAdapter(repo._engine)
    context = adapter.read('alice',None)
    message = SimpleNamespace(content='一份旧回复',raw_payload={'answer_result':{'memory_context':context}})
    assert adapter.permits_history('alice',message)
    adapter.delete_preference('alice',old.memory_id,context['preferences']['response_detail']['revision'])
    assert not adapter.permits_history('alice',message)
