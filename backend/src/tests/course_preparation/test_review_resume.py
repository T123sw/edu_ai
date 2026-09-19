from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from threading import Barrier
import pytest
from sqlalchemy.orm import Session
from app.database.models import PreparationArtifact, MemoryEpoch
from app.course_preparation.artifact_store import ArtifactStore
from app.course_preparation.generation_failures import FailureDetail, GenerationFailure, recovery_scope
from app.course_preparation.lifecycle_repository import StaleLease
from app.course_preparation.tool_registry import digest
from tests.course_preparation.test_generation_adapter import generation, submit


def failure(child, category='review_format'):
    scopes={'review_format':'review','provider':'provider','content':'content','render':'content','contract':'content',
            'permission':'none','budget':'none','canceled':'none'}
    return FailureDetail(code='REVIEW_FIELDS_MISSING',phase='resource_review',category=category,
                         message='缺少逐选项核验项',retry_scope=scopes[category],artifact_id=child['artifact_id'])


def candidate(generation):
    repo, parent, adapter = generation
    _, receipt = submit(generation)
    child = adapter.artifacts.claim('alice', receipt['artifact_id'])
    port = adapter.artifacts.checkpoint_port(child)
    body = {'questions':[{'id':'q1','question':'1+1?','answer':'2'}]}
    port.save_review_candidate(content=body, content_digest=digest(body), spec_digest=child['spec_digest'],
                               review_state={'decision':'pending'})
    return repo, parent, adapter.artifacts, child, body


@pytest.mark.parametrize('category,scope', [('provider','provider'),('review_format','review'),('content','content'),
    ('render','content'),('contract','content'),('permission',None),('budget',None),('canceled',None)])
def test_recovery_matrix_is_typed_and_bounded(category, scope):
    detail=failure({'artifact_id':'a'},category)
    if scope:
        assert recovery_scope(detail)==scope
        with pytest.raises(GenerationFailure): recovery_scope(detail,attempts=2)
    else:
        with pytest.raises(GenerationFailure): recovery_scope(detail)


def test_format_failure_survives_new_store_and_receipt_loss(generation):
    repo,parent,store,child,body=candidate(generation)
    store.fail(child,failure(child))
    assert store.get('alice',child['artifact_id'])['status']=='failed'
    recovered=ArtifactStore(repo)
    receipt=recovered.resume_review(parent,child['artifact_id'],recovery_key='repair-1')
    assert recovered.resume_review(parent,child['artifact_id'],recovery_key='repair-1')==receipt
    next_child=recovered.claim('alice',child['artifact_id'])
    saved=recovered.checkpoint_port(next_child).load_review_candidate()
    assert saved['content']==body and saved['content_digest']==digest(body)
    assert saved['resource_id']==child['resource_id'] and saved['resource_version']==child['resource_version']
    assert saved['recovery_attempt']==1 and receipt['job_id'].endswith('_recovery_1')
    with pytest.raises(ValueError,match='CHANGED_CONTENT'):
        recovered.checkpoint_port(next_child).save_review_candidate(content='rewritten',content_digest=digest('rewritten'),
            spec_digest=child['spec_digest'],review_state={})
    recovered.fail(next_child,failure(next_child))
    recovered.resume_review(parent,child['artifact_id'],recovery_key='repair-2')
    last=recovered.claim('alice',child['artifact_id']);recovered.fail(last,failure(last))
    with pytest.raises(GenerationFailure): recovered.resume_review(parent,child['artifact_id'],recovery_key='repair-3')


def test_crash_after_candidate_write_fences_old_worker(generation):
    repo,parent,store,child,body=candidate(generation)
    with Session(repo.engine) as db,db.begin():
        db.get(PreparationArtifact,child['artifact_id']).lease_until=datetime.now(timezone.utc)-timedelta(seconds=1)
    new=ArtifactStore(repo).claim('alice',child['artifact_id'])
    assert store.checkpoint_port(new).load_review_candidate()['content']==body
    with pytest.raises(StaleLease): store.checkpoint_port(child).load_review_candidate()


def test_cancel_blocks_candidate_and_resume_but_preserves_audit(generation):
    repo,parent,store,child,body=candidate(generation)
    repo.cancel('alice',parent.preparation_id)
    with pytest.raises(StaleLease): store.checkpoint_port(child).load_review_candidate()
    store.fail(child,failure(child))
    with pytest.raises(StaleLease): store.resume_review(parent,child['artifact_id'],recovery_key='r')
    assert store.get('alice',child['artifact_id'],content=True)['content']['_review_candidate']['content']==body
    assert repo.get_public('alice',parent.preparation_id)['result_ref'] is None


def test_explicit_parent_retry_cannot_reuse_old_candidate(generation):
    repo,parent,store,child,_=candidate(generation)
    repo.cancel('alice',parent.preparation_id);store.fail(child,failure(child))
    repo.retry('alice',parent.preparation_id)
    newer=repo.claim('new',preparation_id=parent.preparation_id)
    with pytest.raises(ValueError,match='STALE'):store.resume_review(newer,child['artifact_id'],recovery_key='new')
    with pytest.raises(StaleLease):store.save(child,{'content':'late'})


def test_memory_epoch_change_invalidates_candidate(generation):
    from app.chat.memory.lifecycle import MemoryChanged
    repo,parent,store,child,_=candidate(generation)
    with Session(repo.engine) as db,db.begin():db.get(MemoryEpoch,'alice').epoch+=1
    with pytest.raises(MemoryChanged):store.checkpoint_port(child).load_review_candidate()


def test_two_workers_resume_same_candidate_once(generation):
    repo,parent,store,child,_=candidate(generation)
    if repo.engine.dialect.name!='postgresql':pytest.skip('PostgreSQL row lock competition')
    store.fail(child,failure(child));barrier=Barrier(2)
    def resume():
        barrier.wait()
        return ArtifactStore(repo).resume_review(parent,child['artifact_id'],recovery_key='repair-1')
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(resume) for _ in range(2)]
        assert futures[0].result()==futures[1].result()
    assert store.get('alice',child['artifact_id'],content=True)['content']['_review_candidate']['recovery_attempt']==1


def test_provider_failure_before_body_can_retry_without_fake_candidate(generation):
    repo,parent,adapter=generation;_,receipt=submit(generation)
    store=adapter.artifacts;child=store.claim('alice',receipt['artifact_id'])
    store.fail(child,failure(child,'provider'))
    retry=store.resume_review(parent,child['artifact_id'],recovery_key='provider-1')
    assert retry['retry_scope']=='provider'
    child=store.claim('alice',child['artifact_id'])
    assert store.checkpoint_port(child).load_review_candidate() is None
    store.checkpoint_port(child).save_review_candidate(content='body',content_digest=digest('body'),
        spec_digest=child['spec_digest'],review_state={'decision':'pending'})
    assert store.checkpoint_port(child).load_review_candidate()['recovery_attempt']==1


def test_lost_parent_receipt_reconciles_even_after_child_saved_draft(generation):
    repo,parent,store,child,body=candidate(generation)
    store.fail(child,failure(child))
    receipt=store.resume_review(parent,child['artifact_id'],recovery_key='review-1')
    resumed=store.claim('alice',child['artifact_id'])
    port=store.checkpoint_port(resumed)
    port.save_review_candidate(content=body,content_digest=digest(body),spec_digest=child['spec_digest'],
                               review_state={'decision':'pass'})
    assert store.resume_review(parent,child['artifact_id'],recovery_key='review-1')==receipt
    store.save(resumed,{'content':body,'generation_state':{'resource_review':{'decision':'pass'}}})
    assert store.resume_review(parent,child['artifact_id'],recovery_key='review-1')==receipt


def test_cancel_racing_resume_never_publishes_and_usage_can_settle(generation):
    from app.course_preparation.runtime_contracts import BudgetCost
    repo,parent,store,child,_=candidate(generation)
    if repo.engine.dialect.name!='postgresql':pytest.skip('PostgreSQL row lock competition')
    action=store.begin_action(child,'review-call','model_completion',{},BudgetCost(calls=1,tokens=100))
    # Settle the observed failure before making its candidate available for recovery.
    store.finish_action(child,action['action_id'],{'failed':True},BudgetCost(calls=1,tokens=40),failed=True)
    store.fail(child,failure(child));barrier=Barrier(2)
    def resume():
        barrier.wait()
        try:return store.resume_review(parent,child['artifact_id'],recovery_key='racing-review')
        except StaleLease:return None
    def cancel():barrier.wait();return repo.cancel('alice',parent.preparation_id)
    with ThreadPoolExecutor(max_workers=2) as pool:
        a,b=pool.submit(resume),pool.submit(cancel);a.result();b.result()
    public=repo.get_public('alice',parent.preparation_id)
    assert public['status']=='canceled' and public['result_ref'] is None
    assert public['budget']['consumed']['tokens']==40 and public['budget']['reserved']['tokens']==0
    assert store.get('alice',child['artifact_id'])['status']!='draft'
