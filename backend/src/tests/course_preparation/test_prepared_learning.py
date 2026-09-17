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


def test_historical_node_remains_readable_after_route_replacement(ready):
    from copy import deepcopy
    from app.database.models import PreparedManifestVersion,PreparedCoursePointer
    from app.course_preparation.tool_registry import digest
    from app.self_learning.contracts import ResourceRef
    repo,context,delivery=ready
    result=delivery.commit(context).result_ref; course=result['course_id']
    bridge=PreparedCourses(repo.engine); old=bridge.manifest('alice',course); node=old['nodes'][0]; resource=node['resources'][0]
    with Session(repo.engine) as db,db.begin():
        original=db.get(PreparedManifestVersion,('alice',course,1))
        newer=deepcopy(original.payload);newer['version']=2;newer['route_version']=2;newer['nodes'][0]['node_id']='replacement'
        copied={column.name:getattr(original,column.name) for column in PreparedManifestVersion.__table__.columns}
        copied.update(version=2,payload=newer,content_digest=digest(newer))
        db.add(PreparedManifestVersion(**copied));db.get(PreparedCoursePointer,('alice',course)).version=2
    ref=ResourceRef(course_id=course,material_type=resource['resource_type'],material_id=resource['resource_id'],version=resource['version'])
    assert bridge.historical_topic('alice',course,node['node_id'],ref)==node
    assert bridge.historical_topic('alice',course,node['node_id'],ref.model_copy(update={'version':99})) is None
    with Session(repo.engine) as db,db.begin():db.delete(db.get(CourseMembership,(course,'alice')))
    with pytest.raises(HTTPException):bridge.historical_topic('alice',course,node['node_id'],ref)
