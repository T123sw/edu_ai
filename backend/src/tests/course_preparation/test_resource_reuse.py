from uuid import uuid4
from sqlalchemy.orm import Session
from app.database.models import CourseMembership
from app.course_preparation.artifact_store import ArtifactStore
from app.course_preparation.runtime_contracts import BudgetCost
from app.course_preparation.schemas import PreparationRequest
from tests.course_preparation.test_delivery import ready
from tests.course_preparation.test_generation_adapter import generation


def test_exact_spec_cache_requires_committed_accessible_source(ready):
    repo,context,delivery=ready
    result=delivery.commit(context).result_ref
    original=context.checkpoint['artifacts'][0]
    def create(key):
        task=repo.submit('alice',PreparationRequest(request_id=uuid4(),operation='create_course',goal='重新学习工具'))
        claim=repo.claim('cache',preparation_id=task['preparation_id'])
        action=repo.begin_action(claim,key,'generate_resource',original['spec'],BudgetCost(calls=1))
        return ArtifactStore(repo).create(claim,action['action_id'],original['spec'])
    reused=create('reuse')
    assert reused['status']=='draft' and reused['content_digest']==original['content_digest']
    assert reused['resource_id']!=original['resource_id']
    with Session(repo.engine) as db,db.begin(): db.delete(db.get(CourseMembership,(result['course_id'],'alice')))
    assert create('revoked')['status']=='pending'
