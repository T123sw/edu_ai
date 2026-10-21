"""Real model + browser checks + API persistence, using a fresh SQLite DB only.

Reuses the previously accepted calculator artifact; does not regenerate lessons.
Run from the repository root with the edu-ai environment on PATH.
"""
import json
import os
from pathlib import Path
import tempfile
import time
from uuid import uuid4

from isolated import configure, ROOT

os.environ.pop('PBL_TEST_DATABASE_URL', None)
os.environ['PBL_ACCEPTANCE_STORAGE'] = tempfile.mkdtemp(prefix='pbl-tutor-acceptance-')
storage = configure(live_model=True)

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, update
from app.api import pbl
from app.auth import get_current_user
from app.pbl.db_models import PblExercise, PblWorkspace, PblRun, PblTutorTurn
from app.pbl.repository import PblRepository

engine = create_engine('sqlite:///' + str(storage / 'tutor.db'), connect_args={'check_same_thread': False})
for model in (PblExercise, PblWorkspace, PblRun, PblTutorTurn):
    model.__table__.create(engine)
repo = PblRepository(engine=engine)
row = repo.create_or_get('tutor_acceptance', str(uuid4()), '计算器辅导验收')
artifact = json.loads((ROOT / 'docs/acceptance/2026-10-14-pbl-project-integration/real-model-artifact.json').read_text())
artifact['exerciseId'] = row.id
# Seed the prior accepted public artifact directly into this disposable fixture DB.
with engine.begin() as connection:
    connection.execute(update(PblExercise).where(PblExercise.id == row.id).values(
        artifact_public=artifact, artifact_version=1, template_version='react-app-v1', generation_state='ready'))

app = FastAPI()
app.include_router(pbl.router)
app.dependency_overrides[pbl.repository] = lambda: repo
app.dependency_overrides[get_current_user] = lambda: {'username': 'tutor_acceptance'}
base = f'/api/pbl/{row.id}'
result = {'environment': 'fresh temporary SQLite; prior accepted calculator artifact; fixture identity',
          'model': 'real configured provider', 'browserChecks': 'real server browser runner',
          'productionModified': False}
with TestClient(app) as client:
    before = client.get(base + '/workspace').json()
    request = {'artifactVersion': 1, 'taskId': artifact['tasks'][0]['id'], 'files': artifact['starterFiles']}
    checked = client.post(base + '/check', json={**request, 'runId': str(uuid4())})
    assert checked.status_code == 200, checked.text
    report = checked.json()
    assert report['status'] == 'failed' and report['evidenceSource'] == 'server_verified'
    question = {**request, 'requestId': str(uuid4()), 'question': '请结合本步检查失败结果，告诉我应该先改哪里，只给一个提示，不给完整代码。'}
    started = time.monotonic()
    response = client.post(base + '/tutor', json=question)
    assert response.status_code == 200, response.text
    first = response.json()
    assert first['runId'] == report['runId'] and first['evidenceSource'] == 'server_verified'
    assert client.post(base + '/tutor', json=question).json() == first
    edited = {**question, 'requestId': str(uuid4()), 'files': {**request['files'], '/src/App.jsx': request['files']['/src/App.jsx'] + '\n// 我刚修改过代码'},
              'question': '我修改了代码但没有重新检查，现在能认为这一步通过了吗？'}
    response = client.post(base + '/tutor', json=edited)
    assert response.status_code == 200, response.text
    second = response.json()
    assert second['runId'] is None and second['evidenceSource'] is None
    history = client.get(base + '/tutor', params={'artifactVersion': 1, 'taskId': request['taskId']}).json()
    assert history['items'] == [first, second]
    assert client.get(base + '/workspace').json() == before
    assert len(client.get(base + '/runs').json()['items']) == 1
    result.update(passed=True, elapsedSeconds=round(time.monotonic() - started, 2), report=report,
                  turns=history['items'], retryDeduplicated=True, workspaceUnchanged=True, checksUnchanged=True)
out = ROOT / 'docs/acceptance/2026-10-14-pbl-tutor/real-model.json'
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(result, ensure_ascii=False, indent=2))
print(json.dumps({'passed': True, 'turns': 2, 'evidence': str(out)}, ensure_ascii=False))
engine.dispose()
