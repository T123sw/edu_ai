import importlib.util
import json
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import inspect

from app.api import pbl
from app.auth import get_current_user
from app.pbl.db_models import PblTutorTurn
from app.pbl.repository import WorkspaceConflict
from app.pbl.tutor import TutorQuestion, TutorRepository
from .test_api import client  # noqa: F401
from .test_project_integration import plan, artifact, ready_project, check_request  # noqa: F401
from .test_repository_postgres import pg_engine, pg_repository  # noqa: F401


@pytest.fixture
def question(candidate):
    return {'requestId': str(uuid4()), 'artifactVersion': 1, 'taskId': 'implement-sort',
            'files': {'/src/algorithm.js': candidate.referenceSolution}, 'question': '为什么重复元素丢失了？'}


def test_matching_evidence_only_and_no_private_material(repository, ready_exercise, question, run):
    tutor = TutorRepository(repository)
    before = repository.get_or_create_workspace('alice', ready_exercise.id).model_dump()
    stored_run = repository.append_run('alice', ready_exercise.id, run)
    existing, context = tutor.prepare('alice', ready_exercise.id, TutorQuestion(**question))
    assert existing is None and context['matchingRun']['runId'] == run['runId']
    assert context['matchingRun']['evidenceSource'] == 'browser_reported'
    assert not any(key in json.dumps(context) for key in ('referenceSolution', 'candidate_private', 'checkpoint'))
    edited = TutorQuestion(**{**question, 'files': {'/src/algorithm.js': '// unsaved draft'}})
    assert tutor.prepare('alice', ready_exercise.id, edited)[1]['matchingRun'] is None
    tutor.save('alice', ready_exercise.id, TutorQuestion(**question), context, '先观察重复元素如何分区。')
    assert repository.get_or_create_workspace('alice', ready_exercise.id).model_dump() == before
    assert repository.list_runs('alice', ready_exercise.id) == [stored_run]


def test_project_current_step_server_evidence_and_history_isolation(repository, ready_project, artifact, check_request):
    tutor = TutorRepository(repository)
    payload = TutorQuestion(requestId=uuid4(), artifactVersion=1, taskId=check_request['taskId'],
                            files=check_request['files'], question='检查失败怎么办？')
    _, checks, _ = repository.project_check_input('alice', ready_project.id, check_request)
    report = repository.save_project_check('alice', ready_project.id, check_request, {
        'passed': False, 'durationMs': 1, 'results': [{'caseId': c['id'], 'status': 'failed', 'message': '按钮不存在'} for c in checks]})
    _, context = tutor.prepare('alice', ready_project.id, payload)
    assert context['matchingRun']['runId'] == report['runId']
    assert context['matchingRun']['evidenceSource'] == 'server_verified'
    assert [c['id'] for c in context['checks']] == artifact.tasks[1].cumulativeCheckIds
    assert 'referenceFiles' not in json.dumps(context)
    tutor.save('alice', ready_project.id, payload, context, '先添加按钮。')
    assert len(tutor.history('alice', ready_project.id, 1, payload.taskId)['items']) == 1
    assert tutor.history('alice', ready_project.id, 1, artifact.tasks[0].id)['items'] == []
    other = payload.model_copy(update={'requestId': uuid4(), 'taskId': artifact.tasks[0].id})
    assert tutor.prepare('alice', ready_project.id, other)[1]['matchingRun'] is None


def test_api_retry_reuses_turn_and_rejects_changed_request(client, ready_exercise, question, monkeypatch):
    calls = []
    async def model(owner, context):
        calls.append((owner, context))
        return '先检查等于基准值的元素被放在哪里。'
    monkeypatch.setattr(pbl, 'answer_question', model)
    url = f'/api/pbl/{ready_exercise.id}/tutor'
    first = client.post(url, json=question)
    assert first.status_code == 200, first.text
    assert client.post(url, json=question).json() == first.json()
    assert len(calls) == 1 and calls[0][0] == 'alice'
    assert client.post(url, json={**question, 'question': '另一个问题'}).status_code == 409
    history = client.get(url, params={'artifactVersion': 1, 'taskId': 'implement-sort'}).json()
    assert history['items'] == [first.json()]
    assert 'files' not in first.json() and history['nextCursor'] is None


def test_model_failure_retry_does_not_create_partial_turn(client, repository, ready_exercise, question, monkeypatch):
    async def fail(*args):
        raise RuntimeError('secret upstream details')
    monkeypatch.setattr(pbl, 'answer_question', fail)
    url = f'/api/pbl/{ready_exercise.id}/tutor'
    failed = client.post(url, json=question)
    assert failed.status_code == 502 and 'secret' not in failed.text
    assert TutorRepository(repository).history('alice', ready_exercise.id, 1, 'implement-sort')['items'] == []
    async def success(*args):
        return '检查递归边界。'
    monkeypatch.setattr(pbl, 'answer_question', success)
    assert client.post(url, json=question).status_code == 200


@pytest.mark.parametrize('change,status', [({'artifactVersion': 2}, 409), ({'taskId': 'missing'}, 422),
    ({'files': {'/src/secret.js': 'bad'}}, 422), ({'question': '  '}, 422), ({'owner': 'bob'}, 422),
    ({'files': {'/src/algorithm.js': '中' * 50000}}, 422)])
def test_invalid_context_rejected_before_model(client, ready_exercise, question, monkeypatch, change, status):
    monkeypatch.setattr(pbl, 'answer_question', lambda *args: pytest.fail('must not call model'))
    assert client.post(f'/api/pbl/{ready_exercise.id}/tutor', json={**question, **change}).status_code == status


def test_owner_and_readiness_enforced(client, ready_exercise, exercise, repository, question, monkeypatch):
    monkeypatch.setattr(pbl, 'answer_question', lambda *args: pytest.fail('must not call model'))
    unready = repository.create_or_get('alice', str(uuid4()), '尚未生成')
    assert client.post(f'/api/pbl/{unready.id}/tutor', json=question).status_code == 409
    client.app.dependency_overrides[get_current_user] = lambda: {'username': 'bob'}
    url = f'/api/pbl/{ready_exercise.id}/tutor'
    assert client.post(url, json=question).status_code == 404
    assert client.get(url, params={'artifactVersion': 1, 'taskId': 'implement-sort'}).status_code == 404


def test_history_pagination_and_atomic_duplicate(repository, ready_exercise, question):
    tutor = TutorRepository(repository)
    saved = []
    for i in range(8):
        payload = TutorQuestion(**{**question, 'requestId': str(uuid4()), 'question': str(i)})
        _, context = tutor.prepare('alice', ready_exercise.id, payload)
        saved.append(tutor.save('alice', ready_exercise.id, payload, context, f'提示 {i}'))
    assert len(context['recentTurns']) == 6
    assert tutor.save('alice', ready_exercise.id, payload, context, '并发回答') == saved[-1]
    with pytest.raises(WorkspaceConflict):
        tutor.save('alice', ready_exercise.id, payload.model_copy(update={'question': 'changed'}), context, '冲突')
    first = tutor.history('alice', ready_exercise.id, 1, 'implement-sort', limit=3)
    second = tutor.history('alice', ready_exercise.id, 1, 'implement-sort', cursor=first['nextCursor'], limit=3)
    third = tutor.history('alice', ready_exercise.id, 1, 'implement-sort', cursor=second['nextCursor'], limit=3)
    assert third['items'] + second['items'] + first['items'] == saved
    assert third['nextCursor'] is None
    with pytest.raises(ValueError):
        tutor.history('alice', ready_exercise.id, 1, 'implement-sort', cursor='unknown')


def test_tutor_migration_reversible(engine):
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    PblTutorTurn.__table__.drop(engine)
    path = Path(__file__).parents[2] / 'alembic/versions/20261014_0039_pbl_tutor.py'
    spec = importlib.util.spec_from_file_location('pbl_tutor_migration', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()
            assert 'pbl_tutor_turns' in inspect(connection).get_table_names()
            module.downgrade()
            assert 'pbl_tutor_turns' not in inspect(connection).get_table_names()
            module.upgrade()


@pytest.mark.asyncio
async def test_provider_receives_only_prepared_context(monkeypatch):
    from app.pbl.tutor import answer_question
    from app.practice import service
    calls = []
    async def complete(owner, prompt, **kwargs):
        calls.append((owner, json.loads(prompt), kwargs))
        return '  先运行空数组。  '
    monkeypatch.setattr(service, 'complete', complete)
    assert await answer_question('alice', {'question': '如何验证？'}) == '先运行空数组。'
    assert calls[0][1] == {'question': '如何验证？'} and '不能运行代码' in calls[0][2]['system']


def test_postgres_concurrent_turns_and_json_evidence(pg_repository, pg_engine, candidate, validation_report, question):
    from concurrent.futures import ThreadPoolExecutor
    import threading
    from app.pbl.contracts import public_artifact
    PblTutorTurn.__table__.create(pg_engine)
    repo = pg_repository
    row = repo.create_or_get('alice', str(uuid4()), '快速排序')
    public = public_artifact(candidate, exercise_id=row.id, artifact_version=1, validation_summary=validation_report)
    repo.publish('alice', row.id, row.id, public, {}, validation_report)
    tutor = TutorRepository(repo)
    payload = TutorQuestion(**question)
    barrier = threading.Barrier(2)
    def save(answer):
        existing, context = tutor.prepare('alice', row.id, payload)
        assert existing is None and context['matchingRun'] is None
        barrier.wait()
        return tutor.save('alice', row.id, payload, context, answer)
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(save, ['提示 A', '提示 B']))
    assert results[0] == results[1]
    assert tutor.history('alice', row.id, 1, payload.taskId)['items'] == [results[0]]
    # Validate PostgreSQL JSON access with a matching persisted browser report.
    from app.pbl.contracts import hash_code
    run = {'runId': str(uuid4()), 'exerciseId': row.id, 'artifactVersion': 1,
           'templateVersion': public.templateVersion, 'taskId': payload.taskId,
           'code': candidate.referenceSolution, 'codeHash': hash_code(candidate.referenceSolution),
           'mode': 'check', 'cases': [c.model_dump() for c in candidate.testCases],
           'status': 'error', 'results': [], 'durationMs': 1, 'evidenceSource': 'browser_reported'}
    repo.append_run('alice', row.id, run)
    _, context = tutor.prepare('alice', row.id, payload.model_copy(update={'requestId': uuid4()}))
    assert context['matchingRun']['runId'] == run['runId']


def test_postgres_tutor_migration(pg_engine, pg_repository):
    PblTutorTurn.__table__.create(pg_engine)
    test_tutor_migration_reversible(pg_engine)
