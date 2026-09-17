import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.database.models import User, CourseMembership
from app.self_learning.prepared_courses import PreparedCourses
from tests.course_preparation.test_delivery import ready
from tests.course_preparation.test_generation_adapter import generation


def test_username_bridge_reads_committed_exact_resources_and_revocation(ready):
    repo, context, delivery = ready
    with Session(repo.engine) as session, session.begin():
        session.get(User, 'alice').username = 'alice-login'
    result = delivery.commit(context).result_ref
    bridge = PreparedCourses(repo.engine)
    course = result['course_id']
    assert bridge.list('alice-login') == [course]
    assert bridge.lookup('alice-login', course)[0]['created_by'] == 'alice-login'
    manifest = bridge.manifest('alice-login', course)
    resource = manifest['nodes'][0]['resources'][0]
    assert bridge.material('alice-login', course, resource['resource_type'], resource['resource_id'], 1)['version'] == 1
    assert bridge.lookup('bob', course) is None
    with pytest.raises(HTTPException): bridge.material('bob', course, 'report', resource['resource_id'])
    with Session(repo.engine) as session, session.begin():
        session.delete(session.get(CourseMembership, (course, 'alice')))
    with pytest.raises(HTTPException): bridge.manifest('alice-login', course)
    assert bridge.list('alice-login') == []
