from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import course_research as api
from app.course_preparation.research_repository import ResearchRepository
from tests.course_preparation.test_research_flow import request


def test_submit_poll_cancel_and_validation(db_engine):
    app = FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[api.current_user] = lambda: {'username': 'alice'}
    app.dependency_overrides[api.repository] = lambda: ResearchRepository(db_engine)
    app.dependency_overrides[api.config_snapshot] = lambda: lambda owner: {}
    client = TestClient(app)
    prefix = '/api/course-preparations/research-runs'
    payload = request().model_dump(mode='json')
    accepted = client.post(prefix, json=payload)
    assert accepted.status_code == 202
    run_id = accepted.json()['run_id']
    assert client.post(prefix, json=payload).json()['run_id'] == run_id
    assert client.get(prefix + '/' + run_id).json()['status'] == 'queued'
    assert client.post(prefix, json={**payload, 'goal': 'different'}).status_code == 409
    assert client.post(prefix, json={**payload, 'owner_user_id': 'bob'}).status_code == 422
    app.dependency_overrides[api.current_user] = lambda: {'username': 'bob'}
    assert client.get(prefix + '/' + run_id).status_code == 404
    assert client.post(prefix + '/' + run_id + '/cancel').status_code == 404
    app.dependency_overrides[api.current_user] = lambda: {'username': 'alice'}
    assert client.post(prefix + '/' + run_id + '/cancel').json()['status'] == 'canceled'


def test_missing_auth_and_disabled_feature():
    app = FastAPI()
    app.include_router(api.router)
    client = TestClient(app)
    assert client.get('/api/course-preparations/research-runs/nope').status_code == 401
