from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import self_learning as api
from app.auth import get_current_user


@pytest.mark.parametrize('role', ['student', 'teacher', 'admin', 'user', None])
@pytest.mark.parametrize('membership', ['owner', 'editor', 'viewer'])
def test_sharing_depends_on_course_ownership_not_account_role(role, membership):
    user = {'username': 'alice'}
    if role is not None:
        user['role'] = role
    manager = Mock()
    manager.list_generated_materials.side_effect = [[], [{'material_id': 'existing'}]]
    svc = SimpleNamespace(
        require=Mock(return_value=(None, SimpleNamespace(role=membership))),
        manager=manager, store=Mock(),
    )
    app = FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[api.service] = lambda: svc
    with TestClient(app) as client:
        response = client.post('/api/self-learning/courses/course/publish')
    if membership == 'owner':
        assert response.status_code == 200, response.text
        svc.store.put.assert_called_once_with('__published__', 'course', {'published': True, 'course_id': 'course'})
    else:
        assert response.status_code == 403
        manager.list_generated_materials.assert_not_called()
        svc.store.put.assert_not_called()
    svc.require.assert_called_once_with('course', 'alice')
