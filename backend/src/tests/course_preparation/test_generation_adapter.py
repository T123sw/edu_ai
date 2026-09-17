from datetime import datetime,timezone,timedelta
from uuid import uuid4
import pytest
from sqlalchemy.orm import Session
from app.database import Base
from app.database.models import PreparationArtifact
from app.course_preparation.lifecycle_repository import LifecycleRepository,StaleLease
from app.course_preparation.runtime_contracts import BudgetCost
from app.course_preparation.schemas import PreparationRequest
from app.course_preparation.generation_contracts import ResourceSpec
from app.course_preparation.adapters.generation import GenerationAdapter,automatic_payload
from app.course_preparation.artifact_store import ArtifactStore
from app.chat.tasks.task_store import TaskStore


@pytest.fixture
def generation(runtime_engine,tmp_path):
    names=['agent_memory_epochs','agent_memory_dependencies','agent_memory_items','agent_memory_suppressions','preparation_artifacts']
    Base.metadata.create_all(runtime_engine,tables=[Base.metadata.tables[n] for n in names])
    class Auth:
        def authorize(self,*args): pass
    repo=LifecycleRepository(runtime_engine,authorizer=Auth())
    task=repo.submit('alice',PreparationRequest(request_id=uuid4(),operation='create_course',goal='面试准备'))
    context=repo.claim('parent',preparation_id=task['preparation_id'])
    store=TaskStore(db_path=str(tmp_path/'queue.db'))
    return repo,context,GenerationAdapter(repo,store)


def spec():
    return ResourceSpec(node_id='tools',title='工具调用',resource_type='report',objectives=['解释工具调用'],objective_ids=['tools:o1'],
        evidence=[{'source_id':'s1','quote':'真实引用内容','claim':'工具调用依据','url':'https://example.edu'}],language='zh-CN',audience='面试者',minutes=10,
        learning_check='解释模型与工具的职责',memory_subject='alice',memory_refs={},memory_epoch=0).model_dump(mode='json')


def submit(generation):
    repo,context,adapter=generation
    action=repo.begin_action(context,'generate','generate_resource',spec(),BudgetCost(calls=1))
    receipt=adapter.submit(context,spec(),action['action_id'])
    return action,receipt


def test_unknown_submission_reconciles_same_draft_and_job(generation):
    repo,context,adapter=generation; action,receipt=submit(generation)
    again=adapter.reconcile(context,spec(),action['action_id'])
    assert again==receipt
    assert adapter.task_store.get_durable(receipt['job_id']).command=={'artifact_id':receipt['artifact_id']}
    payload=automatic_payload(spec(),{'owner_user_id':'alice','resource_id':'r1'})
    assert not hasattr(payload,'confirmed_outline')
    assert payload.preparation_policy=='automatic_personal_draft_v1'


def test_child_uses_parent_budget_while_parent_releases_slot_and_cancel_fences(generation):
    repo,context,adapter=generation; _,receipt=submit(generation)
    repo.release(context,delay_seconds=2)
    store=adapter.artifacts; child=store.claim('alice',receipt['artifact_id'])
    action=store.begin_action(child,'call1','model',{},BudgetCost(calls=1,tokens=100))
    store.finish_action(child,action['action_id'],{'done':True})
    assert repo.get_public('alice',context.preparation_id)['budget']['consumed']['tokens']==100
    repo.cancel('alice',context.preparation_id)
    with pytest.raises(StaleLease): store.begin_action(child,'call2','model',{},BudgetCost(calls=1))
    with pytest.raises(StaleLease): store.save(child,{'content':'late'})


def test_expired_child_cannot_write_after_takeover(generation):
    repo,context,adapter=generation; _,receipt=submit(generation)
    first=adapter.artifacts.claim('alice',receipt['artifact_id'])
    with Session(repo.engine) as session,session.begin():
        session.get(PreparationArtifact,receipt['artifact_id']).lease_until=datetime.now(timezone.utc)-timedelta(seconds=1)
    second=adapter.artifacts.claim('alice',receipt['artifact_id'])
    assert second['lease_token']!=first['lease_token']
    with pytest.raises(StaleLease): adapter.artifacts.save(first,{'content':'late'})


def test_succeeded_job_without_reviewed_content_is_not_ready(generation):
    repo,context,adapter=generation; _,receipt=submit(generation)
    child=adapter.artifacts.claim('alice',receipt['artifact_id'])
    adapter.artifacts.save(child,{'content':'no verified review'})
    with pytest.raises(ValueError,match='REVIEW_MISSING'): adapter.read_result('alice',receipt)
    with Session(repo.engine) as session,session.begin():
        session.get(PreparationArtifact,receipt['artifact_id']).content=None
    with pytest.raises(ValueError,match='CONTENT_MISSING'): adapter.read_result('alice',receipt)
