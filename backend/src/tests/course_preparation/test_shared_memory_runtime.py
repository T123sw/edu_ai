from uuid import uuid4
from sqlalchemy.orm import Session
import pytest
from app.database import Base
from app.course_preparation.lifecycle_repository import LifecycleRepository
from app.course_preparation.runtime_contracts import BudgetCost
from app.course_preparation.schemas import PreparationRequest
from app.course_preparation.adapters.memory import PreparationMemory, ContextRebuilt
from app.chat.memory.repository import SqlAlchemyMemoryRepository
from app.chat.memory.domain import MemoryRecordDraft


def test_preference_delete_rebuilds_dependent_context_without_resetting_budget(runtime_engine):
    names=['agent_memory_items','user_profile_facts','conversation_episodes','agent_memory_audit_events',
        'agent_memory_epochs','agent_memory_suppressions','agent_memory_dependencies','agent_memory_changes']
    Base.metadata.create_all(runtime_engine,tables=[Base.metadata.tables[n] for n in names])
    class Auth:
        def authorize(self,*args): pass
    repo=LifecycleRepository(runtime_engine,authorizer=Auth()); memory=PreparationMemory(repo)
    memories=SqlAlchemyMemoryRepository(runtime_engine)
    fact=memories.upsert_memory(MemoryRecordDraft(subject_user_id='alice',owner_user_id='alice',memory_type='preference',fact_kind='preference',content='简短回答',confidence=1,source_type='conversation',source_id='conv:1',source_span='简短回答',profile_axis='response_detail'))
    request=PreparationRequest(request_id=uuid4(),operation='create_course',goal='学习 Agent 面试')
    task=repo.submit('alice',request); ctx=repo.claim('one',preparation_id=task['preparation_id'])
    checkpoint=memory.prepare(ctx,ctx.checkpoint,request)
    checkpoint.update(research_state={'phase':'research','calls':5,'searches':2,'reads':1},artifacts=[{'draft':'old'}])
    repo.checkpoint(ctx,checkpoint)
    action=repo.begin_action(ctx,'spent','model',{},BudgetCost(calls=1,tokens=100))
    repo.finish_action(ctx,action['action_id'],{'done':True})
    before=repo.get_public('alice',task['preparation_id'])['budget']
    memories.invalidate(memory_id=fact.memory_id,subject_user_id='alice',reason='user_requested')
    with pytest.raises(ContextRebuilt): memory.validate(ctx,checkpoint)
    after=repo.get_public('alice',task['preparation_id'])
    assert after['budget']==before
    resumed=repo.claim('two',preparation_id=task['preparation_id'])
    assert resumed.stage=='normalize'
    assert resumed.checkpoint['research_state']['calls']==5
    assert resumed.checkpoint['invalidated_drafts'][0]['artifacts']==[{'draft':'old'}]
    assert 'memory_view' not in resumed.checkpoint
