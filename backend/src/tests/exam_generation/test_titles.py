from copy import deepcopy
from uuid import uuid4
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from app.database.models import AppStateRecord, DurableTaskModel
from app.database.session import database_session
from app.exam_generation.repository import GenerationRepository, NAMESPACE
from app.exam_generation.titles import paper_title
from app.exam_practice.service import PracticeService, PAPER
from app.exam_practice.contracts import Start, Draft
from test_blueprint_validation import complete_paper

MIMIC = '保持原卷题型、题数和考点，生成一套新的模拟试卷。'
CUSTOM = '根据上传的学习资料，生成一套覆盖主要知识点的习题。'


@pytest.mark.parametrize('mode,requirement,sources,expected', [
    ('mimic', MIMIC, [{'role': 'context', 'filename': '补充.md'}, {'role': 'template', 'filename': '数据结构期末.PDF'}], '数据结构期末 · 模拟试卷'),
    ('custom', CUSTOM, [{'filename': 'Python基础.docx'}], 'Python基础 · 练习题'),
    ('custom', CUSTOM, [{'filename': '第一章.pdf'}, {'filename': '第二章.pdf'}], '第一章等 2 份资料 · 练习题'),
    ('custom', '  python基础联系  ', [{'filename': '无关.pdf'}], 'python基础联系'),
    ('custom', CUSTOM, [{'filename': r'C:\fakepath\循环.与函数.PDF'}], '循环.与函数 · 练习题'),
    ('custom', CUSTOM, [{'filename': '/private/path/ 线性\n代数.md'}], '线性 代数 · 练习题'),
    ('mimic', MIMIC, [], '模拟试卷'),
    ('custom', CUSTOM, [{'filename': '.pdf'}], '练习题'),
    ('custom', '', [{'filename': 'a' * 100 + '.txt'}], 'a' * 59 + '… · 练习题'),
])
def test_filename_titles(mode, requirement, sources, expected):
    assert paper_title({'mode': mode, 'requirement': requirement}, sources) == expected


def test_legacy_title_is_consistent_across_api_and_cached_practice_without_changing_answers(tmp_path, monkeypatch):
    from app.api import exam_generations as api
    from app.auth import get_current_user
    engine = create_engine('sqlite:///' + str(tmp_path / 'titles.db'), connect_args={'check_same_thread': False})
    AppStateRecord.__table__.create(engine)
    DurableTaskModel.__table__.create(engine)
    repo, practice = GenerationRepository(engine), PracticeService(engine)
    data = complete_paper()
    data.update(id='paper1', job_id='job1', last_seq=0,
                sources=[{'role': 'template', 'filename': '数据结构期末.pdf', 'source_hash': 'PRIVATE_HASH'}])
    data['request'].update(requirement=MIMIC, request_id=str(uuid4()))
    original = deepcopy(data)
    with database_session(engine=engine) as db:
        db.add(AppStateRecord(namespace=NAMESPACE, record_key='paper1', owner_user_id='alice', payload=data))
    first = practice.paper('alice', 'paper1')
    run = practice.start('alice', 'paper1', Start(request_id=uuid4()))
    practice.draft('alice', 'paper1', run['id'], 'q_0',
                   Draft(answer={'option_ids': ['A'], 'blank_values': [], 'text': ''}, expected_revision=0))
    saved_run = practice.get_run('alice', 'paper1', run['id'])
    # Simulate a snapshot opened before this title policy was introduced.
    with database_session(engine=engine) as db:
        snapshot = db.get(AppStateRecord, (PAPER, 'paper1'))
        payload = deepcopy(snapshot.payload)
        payload['paper']['title'] = MIMIC
        snapshot.payload = payload
    reopened = practice.paper('alice', 'paper1')
    assert reopened['title'] == first['title'] == '数据结构期末 · 模拟试卷'
    assert reopened['version'] == first['version']
    assert reopened['questions'] == first['questions']
    assert practice.get_run('alice', 'paper1', run['id']) == saved_run
    assert repo.get('alice', 'paper1', include_events=False) == original
    app = FastAPI()
    app.include_router(api.router)
    actor = {'username': 'alice'}
    app.dependency_overrides[get_current_user] = lambda: actor
    app.dependency_overrides[api.repository] = lambda: repo
    monkeypatch.setattr(api, 'get_job', lambda _: None)
    with TestClient(app) as client:
        for path in ['', '/paper1', '/paper1/paper']:
            response = client.get('/api/exam-generations' + path)
            assert response.status_code == 200
            assert 'PRIVATE_HASH' not in response.text
            value = response.json()['items'][0] if path == '' else response.json()
            assert value['title'] == reopened['title']
        actor['username'] = 'bob'
        assert client.get('/api/exam-generations').json()['items'] == []
        assert client.get('/api/exam-generations/paper1').status_code == 404
    engine.dispose()
