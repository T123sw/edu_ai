import asyncio
from uuid import uuid4
import pytest
from app.self_learning.summary_service import SummaryService
from tests.self_learning.test_memory_lifecycle import memory, agent_service, live_service, repository, put


def histories(memory):
    repo = memory.learning.session_repository
    session = repo.ensure_session('alice', 'course', 'a', '导学')
    with repo._write(session['session_id']) as db:
        row = repo._owned(db, 'alice', session['session_id'])
        for n in range(16):
            repo._append(db, row, f'u{n}', 'user', f'解释变量{n}', 'user_content', {'request_id':str(n)})
            repo._append(db, row, f'a{n}', 'assistant', f'解释{n}', 'assistant_content', {'request_id':str(n)})
    return session['session_id']


def test_summary_preserves_raw_history_and_validates_sources(memory):
    sid = histories(memory)
    service = SummaryService(memory.learning, memory.engine, memory)
    packet = service.prepare('alice', sid)
    assert packet and len(packet['messages']) == 24  # keep last four full turns
    bad = {'items':[{'text':'编造', 'source_ids':['foreign'], 'kind':'fact'}]}
    with pytest.raises(ValueError):
        service.commit(packet, bad)
    result = {'items':[{'text':'讨论变量', 'source_ids':['u0','a0'], 'kind':'fact'}]}
    assert service.commit(packet, result)
    assert not service.commit(packet, result)  # CAS prevents late rewrite
    assert service.read('alice', sid)['items'][0]['text'] == '讨论变量'
    assert len(memory.learning.session_repository.messages('alice', sid, limit=100)['items']) == 33


def test_deleted_preference_fences_old_summary_and_source(memory):
    sid = histories(memory)
    first = put(memory, source='u0')
    service = SummaryService(memory.learning, memory.engine, memory)
    packet = service.prepare('alice', sid)
    memory.delete('alice', 'course', 'example_order', 'course', first['revision'], operation_id='delete-summary')
    assert not service.commit(packet, {'items':[{'text':'先举例', 'source_ids':['u0'], 'kind':'fact'}]})
    assert service.read('alice', sid) is None
    assert all(m['id'] != 'u0' for m in service.prepare('alice', sid)['messages'])

def test_background_summary_calls_model_without_tools(memory, monkeypatch):
    import json
    from app.self_learning.check_service import CheckService
    from app.self_learning.model_adapter import LearningModelAdapter
    from app.services.runtime_config_resolver import runtime_config_resolver
    sid = histories(memory)
    calls = []
    class Model:
        async def complete(self, messages, tools, deadline):
            calls.append(tools)
            return {'calls':[], 'content':json.dumps({'items':[{'text':'变量讨论','source_ids':['u0','a0'],'kind':'fact'}]})}
    monkeypatch.setattr(runtime_config_resolver, 'resolve', lambda *args, **kwargs: {})
    monkeypatch.setattr(LearningModelAdapter, 'from_config', lambda *_: Model())
    memory.learning.checks = CheckService(memory.learning, memory.engine)
    service = SummaryService(memory.learning, memory.engine, memory)
    assert asyncio.run(service.summarize('alice', sid))
    assert calls == [[]]
    assert service.read('alice', sid)['items'][0]['text'] == '变量讨论'
