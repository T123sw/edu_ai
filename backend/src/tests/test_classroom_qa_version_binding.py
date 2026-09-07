from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.classroom_qa import submit_classroom_qa_turn
from app.schemas.classroom_qa import ClassroomQaTurnRequest


pytestmark = pytest.mark.anyio


def request():
    return ClassroomQaTurnRequest(
        client_turn_id=uuid4(), question='为什么？', resource_version=2,
        checkpoint={'scene_id': 's1', 'scene_index': 0, 'action_index': 0,
                    'action_id': 'a1', 'phase': 'executing_action', 'page_revision': 1},
    )


async def test_qa_loads_the_player_version_with_the_same_principal(monkeypatch):
    from app.api import courses
    principal = SimpleNamespace(user_id='student-a', course_role='viewer')
    snapshot = {'title': '已发布第 2 版', 'scenes': []}
    def load(**kwargs):
        assert kwargs['resource_version'] == 2
        assert kwargs['principal'] is principal
        return snapshot
    async def submit(**kwargs):
        assert kwargs['trusted_material'] is snapshot
        return {'ok': True}
    monkeypatch.setattr(courses, 'get_classroom', load)
    result = await submit_classroom_qa_turn('course-1', 'classroom-1', request(), principal, SimpleNamespace(submit_turn=submit))
    assert result == {'ok': True}


async def test_unavailable_version_is_rejected_before_answer_generation(monkeypatch):
    from app.api import courses
    def load(**kwargs):
        raise HTTPException(status_code=404, detail='课件版本不可用')
    async def submit(**kwargs):
        pytest.fail('An unauthorized version must not reach answer generation')
    monkeypatch.setattr(courses, 'get_classroom', load)
    with pytest.raises(HTTPException) as error:
        await submit_classroom_qa_turn('course-1', 'classroom-1', request(), SimpleNamespace(user_id='student-a'), SimpleNamespace(submit_turn=submit))
    assert error.value.status_code == 404
