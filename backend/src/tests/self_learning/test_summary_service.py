from types import SimpleNamespace
from sqlalchemy.orm import Session
import pytest
from app.database import Base,ConversationMessage
from app.self_learning.summary_service import SummaryService
from app.self_learning.db_models import LearningTopicSession
from app.chat.memory.repository import SqlAlchemyMemoryRepository
from app.chat.memory.lifecycle import MemoryChanged
from tests.chat.memory.test_memory_lifecycle import draft
from tests.self_learning.test_session_repository import repository


@pytest.fixture
def summary(repository):
    names=['learning_summaries','agent_memory_epochs','agent_memory_items','agent_memory_suppressions','agent_memory_dependencies',
           'agent_memory_changes','user_profile_facts','agent_memory_audit_events']
    Base.metadata.create_all(repository.engine,tables=[Base.metadata.tables[n] for n in names])
    session=repository.ensure_session('alice','course','a','导学',[])
    with repository._write(session['session_id']) as db:
        row=db.get(LearningTopicSession,session['session_id'])
        for i in range(30): repository._append(db,row,'msg-'+str(i),'user','学习提问 '+str(i),'user_content')
    learning=SimpleNamespace(session_repository=repository,require=lambda course,owner:None)
    return SummaryService(learning),session['session_id']


def test_summary_cas_preserves_recent_and_all_original_messages(summary):
    service,sid=summary
    first=service.capture('alice',sid)
    assert len(first['messages'])==19
    second=service.capture('alice',sid)
    service.publish(first,'早期问题的摘要')
    with pytest.raises(ValueError,match='REVISION_CHANGED'): service.publish(second,'迟到旧摘要')
    assert service.read('alice',sid)['summary']=='早期问题的摘要'
    with Session(service.engine) as db:
        assert len(db.query(ConversationMessage).all())==31
    with pytest.raises(PermissionError): service.read('bob',sid)


def test_deleted_preference_invalidates_old_summary_and_late_publish(summary):
    service,sid=summary
    repo=SqlAlchemyMemoryRepository(service.engine)
    preference=repo.upsert_memory(draft())
    snapshot=service.capture('alice',sid)
    service.publish(snapshot,'依据当时偏好的摘要')
    late=service.capture('alice',sid)
    repo.invalidate(memory_id=preference.memory_id,subject_user_id='alice',reason='user_requested')
    assert service.read('alice',sid) is None
    with pytest.raises(MemoryChanged): service.publish(late,'迟到的旧偏好摘要')
