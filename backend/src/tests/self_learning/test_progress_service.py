import pytest
from fastapi import HTTPException
from app.self_learning.contracts import Actor
from app.self_learning.course_reader import CourseReader
from app.self_learning.progress_service import ProgressService
from tests.self_learning.test_progress_repository import progress, repository, event


def test_scope_rechecked_before_replay_and_optional_not_core(progress):
    allowed = [True]
    def authorize(*_):
        if not allowed[0]:
            raise HTTPException(404)
    manifest = dict(course_id='course', manifest_id='manifest', version=1, route_version=1, nodes=[
        dict(node_id='a', title='A', resources=[dict(resource_type='report', resource_id='doc', version=1, required=True),
            dict(resource_type='report', resource_id='optional', version=1, required=False)]),
        dict(node_id='b', title='B', resources=[dict(resource_type='report', resource_id='next', version=1, required=True)])])
    reader = CourseReader(authorize=authorize, load_manifest=lambda *_: manifest,
        load_legacy=lambda *_: None, load_resource=lambda _, ref: {'version': ref.version})
    svc = ProgressService(reader, progress)
    e = event()
    actor = Actor(user_id='alice')
    first = svc.record(actor, 'course', 'a', e)
    assert svc.record(actor, 'course', 'a', e) == first
    projection = svc.read(actor, 'course')
    assert projection['topics'][0]['progress'] == 'core_completed'
    assert projection['topics'][0]['judgment'] == 'unverified'
    assert projection['next_actions']['a'][0]['resource_ref']['material_id'] == 'next'
    with pytest.raises(HTTPException):
        svc.record(actor, 'course', 'b', event())
    allowed[0] = False
    with pytest.raises(HTTPException):
        svc.record(actor, 'course', 'a', e)
