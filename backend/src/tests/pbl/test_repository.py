from uuid import uuid4
import copy
import pytest
from app.pbl.repository import NotFound,WorkspaceConflict,StaleGeneration
from app.pbl.contracts import public_artifact


def test_create_idempotent_topic_and_owner(repository):
    request=str(uuid4())
    first=repository.create_or_get('alice',request,'快速排序')
    assert repository.create_or_get('alice',request,'快速排序').id==first.id
    with pytest.raises(WorkspaceConflict): repository.create_or_get('alice',request,'快排')
    assert repository.create_or_get('bob',request,'快速排序').id!=first.id
    with pytest.raises(NotFound): repository.get_owned('bob',first.id)


def test_not_ready(repository,exercise):
    with pytest.raises(WorkspaceConflict): repository.get_or_create_workspace('alice',exercise.id)


def test_workspace_cas_idempotency_and_versions(repository,ready_exercise,patch):
    first=repository.get_or_create_workspace('alice',ready_exercise.id)
    assert first.revision==0
    saved=repository.save_workspace('alice',ready_exercise.id,patch)
    assert saved.revision==1
    assert repository.save_workspace('alice',ready_exercise.id,patch)==saved
    with pytest.raises(WorkspaceConflict): repository.save_workspace('alice',ready_exercise.id,{**patch,'customInputText':'[2]'})
    with pytest.raises(WorkspaceConflict): repository.save_workspace('alice',ready_exercise.id,{**patch,'mutationId':str(uuid4())})
    with pytest.raises(WorkspaceConflict): repository.save_workspace('alice',ready_exercise.id,{**patch,'artifactVersion':2})
    second={**patch,'expectedRevision':1,'mutationId':str(uuid4()),'customInputText':'[1]'}
    repository.save_workspace('alice',ready_exercise.id,second)
    with pytest.raises(WorkspaceConflict): repository.save_workspace('alice',ready_exercise.id,patch)
    assert repository.get_or_create_workspace('alice',ready_exercise.id).files==patch['files']


def test_run_immutable_and_hash(repository,ready_exercise,run):
    stored=repository.append_run('alice',ready_exercise.id,run)
    assert repository.append_run('alice',ready_exercise.id,run)==stored
    with pytest.raises(WorkspaceConflict):repository.append_run('alice',ready_exercise.id,{**run,'durationMs':13})
    with pytest.raises(ValueError):repository.append_run('alice',ready_exercise.id,{**run,'code':'modified'})
    assert len(repository.list_runs('alice',ready_exercise.id))==1

@pytest.mark.parametrize('change',[
    lambda p:p.update(results=p['results'][:-1]),
    lambda p:p['results'].append(p['results'][0]),
    lambda p:p['results'][0].update(returnedSameReference=True),
    lambda p:p['results'][0].update(actual=[999]),
    lambda p:p.update(cases=p['cases'][:-1]),
    lambda p:p.update(templateVersion='bad'),
    lambda p:p.update(evidenceSource='server_verified'),
])
def test_bad_run_rejected(repository,ready_exercise,run,change):
    change(run)
    with pytest.raises(ValueError): repository.append_run('alice',ready_exercise.id,run)


def test_cross_owner_all_storage_routes(repository,ready_exercise,patch,run):
    for operation in [lambda:repository.get_owned('bob',ready_exercise.id),
        lambda:repository.get_or_create_workspace('bob',ready_exercise.id),
        lambda:repository.save_workspace('bob',ready_exercise.id,patch),
        lambda:repository.append_run('bob',ready_exercise.id,run),
        lambda:repository.list_runs('bob',ready_exercise.id)]:
        with pytest.raises(NotFound):operation()
    assert repository.list_owned('bob')==[]


def test_retry_claim_fences_old_job(repository,exercise,candidate,validation_report):
    assert repository.claim_generation('alice',exercise.id,exercise.current_job_id)
    assert repository.claim_generation('alice',exercise.id,'retry1',exercise.current_job_id)
    assert not repository.claim_generation('alice',exercise.id,'retry2',exercise.current_job_id)
    with pytest.raises(StaleGeneration): repository.save_checkpoint('alice',exercise.id,exercise.current_job_id,{'stage':'old'})
    artifact=public_artifact(candidate,exercise_id=exercise.id,artifact_version=1,validation_summary=validation_report)
    with pytest.raises(StaleGeneration):repository.publish('alice',exercise.id,exercise.current_job_id,artifact,{},validation_report)
    repository.publish('alice',exercise.id,'retry1',artifact,{},validation_report)
    repository.publish('alice',exercise.id,'retry1',artifact,{},validation_report)
    assert not repository.claim_generation('alice',exercise.id,'retry3','retry1')
