import json
from types import SimpleNamespace

import pytest
from core.config import Config
from core.course_storage import CourseStorageManager
from core.conversation_storage import ConversationStorage
from app.artifact_revision.service import ArtifactRevisionService
from app.artifact_revision.jobs import ArtifactRevisionCommandService, ArtifactRevisionTaskHandler
from app.chat.tasks.task_store import TaskStore
from app.services.durable_task_executor import DurableTaskExecutor
from app.services.durable_task_handlers import DurableTaskHandlerRegistry
from app.services.job_completion_service import JobCompletionService
from app.services.job_store import get_job, JobStatus, cancel_job


class Model:
    def __init__(self):
        self.calls = 0
        self.output = {'edits': [{'path': [], 'before': '旧案例', 'after': '新案例'}]}
    def invoke(self, prompt):
        self.calls += 1
        return SimpleNamespace(content=json.dumps(self.output, ensure_ascii=False))


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    for key in ('MATERIAL', 'JOB', 'TASK', 'CONVERSATION', 'KNOWLEDGE', 'APP_STATE'):
        monkeypatch.setenv(key + '_PERSISTENCE_MODE', 'json')
    monkeypatch.setattr(Config, 'STORAGE_ROOT', tmp_path / 'jobs')
    manager = CourseStorageManager(str(tmp_path / 'courses'))
    manager.save_generated_material('course', 'report', 'report1', {'title': '测试报告', 'content': '保留原文\n旧案例'}, owner_user_id='teacher', visibility='private')
    conversations = ConversationStorage(tmp_path / 'conversations.json')
    conversations.ensure_conversation('conv', '修改', owner='teacher')
    store = TaskStore(str(tmp_path / 'tasks.db'))
    model = Model()
    registry = DurableTaskHandlerRegistry()
    handler = ArtifactRevisionTaskHandler(manager, conversations, model, authorize=lambda req: None)
    registry.register('artifact_revision', 1, handler)
    completion = JobCompletionService(task_store=store, course_storage_manager=manager)
    executor = DurableTaskExecutor(task_store=store, handler_registry=registry, completion_service=completion)
    service = ArtifactRevisionService(manager, submitter=ArtifactRevisionCommandService(store).submit)
    ref = {'artifact_type': 'report', 'artifact_id': 'report1', 'version_id': 'v1', 'source_course_id': 'course'}
    def submit(question='将旧案例替换为新案例', operation='op1', pending=None):
        return service.run(owner_user_id='teacher', conversation_id='conv', course_id='course',
            question=question, operation_id=operation, artifact_reference=ref, pending=pending)
    yield SimpleNamespace(**locals())
    store.close()


def test_queue_worker_saves_new_version_and_original_copy(runtime):
    r=runtime
    queued=r.submit()
    assert queued['status']=='queued'
    assert r.model.calls==0
    assert get_job(queued['task_id']).status==JobStatus.QUEUED
    assert r.submit()['task_id']==queued['task_id']
    assert r.executor.run_once()
    job=get_job(queued['task_id'])
    assert job.status==JobStatus.SUCCEEDED
    assert job.kind.value=='revise_artifact'
    assert job.result_ref['version']==2 and job.result_ref['base_version']==1
    storage=ArtifactRevisionService(r.manager).storage
    assert storage.version('course','report','report1','teacher',1)['content']=='保留原文\n旧案例'
    assert storage.version('course','report','report1','teacher',2)['content']=='保留原文\n新案例'
    task=r.store.get_durable(queued['task_id'])
    assert task.result['artifact_revision']['status']=='completed'
    assert '打开资料' in task.result['message']['content']
    assert r.store.get(queued['task_id'],owner_user_id='other') is None


def test_clarification_is_not_advertised_as_saved_material_and_continues(runtime):
    r=runtime
    r.model.output={'question':'希望改哪段？'}
    first=r.submit('不太好')
    assert r.executor.run_once()
    assert get_job(first['task_id']).result_ref['resource_type']=='artifact_conversation'
    pending=r.conversations.get_state('conv')['pending_operation']['revision_pending']
    assert r.manager.get_generated_material('course','report','report1',owner_user_id='teacher')['version']==1
    r.model.output={'edits':[{'path':[],'before':'旧案例','after':'新案例'}]}
    second=r.submit('替换旧案例',pending=pending)
    assert second['task_id']!=first['task_id']
    assert r.executor.run_once()
    assert get_job(second['task_id']).status==JobStatus.SUCCEEDED


def test_model_failure_and_cancellation_keep_original(runtime):
    r=runtime
    r.model.output={'edits':[]}
    first=r.submit()
    r.executor.run_once()
    assert get_job(first['task_id']).status==JobStatus.FAILED
    assert r.manager.get_generated_material('course','report','report1',owner_user_id='teacher')['version']==1
    second=r.submit(operation='op2')
    cancel_job(second['task_id'], owner_user_id='teacher')
    r.store.request_cancel(second['task_id'], owner_user_id='teacher')
    r.executor.run_once()
    assert get_job(second['task_id']).status==JobStatus.CANCELED
    assert r.model.calls==2


def test_shared_stream_returns_task_before_model_runs(runtime):
    from app.chat.application.reply_service_v2 import ReplyServiceV2
    from app.chat.persistence.conversation_store_adapter import ConversationStoreAdapter
    r=runtime
    service=ReplyServiceV2(conversation_store=ConversationStoreAdapter(storage=r.conversations), artifact_revision_service=r.service)
    events=list(service.reply_stream(SimpleNamespace(owner='teacher', actor_role='teacher', course_id='course', conversation_id='conv', question='替换旧案例', artifact_reference=r.ref)))
    submitted=next(e['payload'] for e in events if e['type']=='task_submitted')
    assert submitted['workflow_type']=='artifact_revision'
    assert r.model.calls==0
    assert r.executor.run_once()
    assert r.store.get(submitted['task_id'],owner_user_id='teacher')['result']['artifact_revision']['status']=='completed'


def test_failed_task_retry_uses_same_operation_without_duplicate_versions(runtime):
    from app.services.job_retry_service import retry_durable_job
    r=runtime
    r.model.output={'edits':[]}
    first=r.submit()
    r.executor.run_once()
    retried=retry_durable_job(get_job(first['task_id']),owner_user_id='teacher',task_store=r.store)
    r.model.output={'edits':[{'path':[],'before':'旧案例','after':'新案例'}]}
    assert r.executor.run_once()
    assert get_job(retried.edu_job_id).status==JobStatus.SUCCEEDED
    assert r.manager.get_generated_material('course','report','report1',owner_user_id='teacher')['version']==2


def test_queued_target_version_conflict_does_not_overwrite_newer_copy(runtime):
    r=runtime
    queued=r.submit()
    original=ArtifactRevisionService(r.manager,r.model)
    manual=original.run(owner_user_id='teacher',conversation_id='other',course_id='course',question='修改案例',operation_id='other-op',artifact_reference=r.ref)
    assert manual['status']=='completed'
    assert r.executor.run_once()
    assert get_job(queued['task_id']).error_code=='REVISION_CONFLICT'
    assert r.manager.get_generated_material('course','report','report1',owner_user_id='teacher')['version']==2
