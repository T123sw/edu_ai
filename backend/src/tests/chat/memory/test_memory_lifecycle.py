import pytest
from sqlalchemy import create_engine
from app.database import Base
from app.chat.memory.domain import MemoryRecordDraft
from app.chat.memory.repository import SqlAlchemyMemoryRepository
from app.chat.memory.lifecycle import MemoryChanged, MemorySuppressed


@pytest.fixture
def repo():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    yield SqlAlchemyMemoryRepository(engine)
    engine.dispose()


def draft(**kw):
    return MemoryRecordDraft(subject_user_id='alice', owner_user_id='alice', memory_type='preference',
        fact_kind='preference', content=kw.pop('content', '讲解简洁'), confidence=1,
        source_type='conversation', source_id=kw.pop('source_id','conversation:1'), source_span='讲解简洁',
        profile_axis=kw.pop('profile_axis','response_detail'), **kw)


def test_old_delete_increments_epoch_suppresses_all_evidence_and_invalidates_only_dependents(repo):
    a = repo.upsert_memory(draft())
    a = repo.upsert_memory(draft(source_id='conversation:2'))
    b = repo.upsert_memory(draft(content='中文', source_id='conversation:3', profile_axis='language'))
    life = repo.lifecycle
    view = life.read_effective('alice')
    facts = view['preferences']
    for consumer, axis in [('affected','response_detail'), ('unaffected','language')]:
        fact = facts[axis]
        life.register_dependencies('alice', consumer, {fact['memory_id']:fact['revision']}, expected_epoch=view['memory_epoch'])
    repo.invalidate(memory_id=a.memory_id, subject_user_id='alice', reason='user_deleted')
    assert life.current_epoch('alice') == view['memory_epoch']+1
    with pytest.raises(MemoryChanged): life.validate_consumer('alice','affected')
    assert life.validate_consumer('alice','unaffected') == life.current_epoch('alice')
    for source in ('conversation:1','conversation:2'):
        with pytest.raises(MemorySuppressed): repo.upsert_memory(draft(source_id=source))
    assert list(life.read_effective('alice')['preferences']) == ['language']


def test_late_extraction_and_missing_dependencies_are_rejected(repo):
    epoch = repo.lifecycle.current_epoch('alice')
    repo.upsert_memory(draft(source_id='new', content='详细说明', supersedes_axis=True))
    with pytest.raises(MemoryChanged): repo.upsert_memory(draft(expected_epoch=epoch))
    with pytest.raises(MemoryChanged): repo.lifecycle.validate_consumer('alice','missing')


def test_cross_course_and_cross_owner_preferences_never_leak(repo):
    repo.upsert_memory(draft(course_id='private-course'))
    assert repo.lifecycle.read_effective('alice')['preferences'] == {}
    assert repo.lifecycle.read_effective('bob',course_id='private-course')['preferences'] == {}
    assert repo.lifecycle.read_effective('alice',course_id='private-course')['preferences']


def test_background_extraction_cannot_restore_preference_after_old_api_delete(repo):
    from app.chat.memory.service import AgentMemoryService
    from app.chat.memory.domain import CandidateExtractionResult, MemoryCandidate
    from app.chat.memory.settings import AgentMemorySettings
    old = repo.upsert_memory(draft())
    epoch = repo.lifecycle.current_epoch('alice')
    repo.invalidate(memory_id=old.memory_id, subject_user_id='alice', reason='user_deleted')
    candidate = MemoryCandidate(memory_type='preference', content='讲解简洁', confidence=1,
        source_span='讲解简洁', profile_axis='response_detail', reason='explicit_preference')
    class Extractor:
        def extract_candidates(self, **kwargs):
            return CandidateExtractionResult(provider='langmem', status='ok', candidates=[candidate])
    service = AgentMemoryService(repository=repo, settings=AgentMemorySettings(embedding_enabled=False), langmem_adapter=Extractor())
    service._persist_langmem_background(subject_user_id='alice', conversation_id='late', course_id=None,
        messages=[{'role':'user','content':'讲解简洁'}], policy_hint={}, expected_epoch=epoch)
    assert repo.lifecycle.read_effective('alice')['preferences'] == {}


def test_explicit_confirmation_after_delete_uses_new_source(repo):
    from app.chat.memory.service import AgentMemoryService
    service = AgentMemoryService(repository=repo)
    a = service.confirm_profile_fact(actor='alice', profile_axis='language', value='中文')
    repo.invalidate(memory_id=a.memory_id, subject_user_id='alice', reason='deleted')
    b = service.confirm_profile_fact(actor='alice', profile_axis='language', value='中文')
    assert b.status == 'active'
    assert b.source_id != a.source_id


def test_change_outbox_cleans_only_invalid_index_and_is_replay_safe(repo):
    from sqlalchemy.orm import Session
    from app.database.models import AgentMemoryItem
    old=repo.upsert_memory(draft(embedding=[1.0,0.0],embedding_model='test'))
    repo.invalidate(memory_id=old.memory_id,subject_user_id='alice',reason='user_deleted')
    assert repo.search(subject_user_id='alice',course_id=None,query='讲解简洁',limit=5)==[]
    assert repo.lifecycle.consume_changes()>0
    assert repo.lifecycle.consume_changes()==0
    with Session(repo._engine) as db:
        row=db.get(AgentMemoryItem,old.memory_id)
        assert row.embedding is None and row.content=='讲解简洁'
