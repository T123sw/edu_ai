from copy import deepcopy

import pytest

from app.self_learning.contracts import Actor, ResourceRef
from app.self_learning.course_reader import CourseReader, CourseAccessDenied, ResourceVersionUnavailable


@pytest.fixture
def catalog():
    return {
        'manifest': None,
        'legacy': {'id': 'course', 'goal': '学习', 'chapters': [
            {'id': 'a', 'title': '变量', 'resources': [
                {'id': 'same', 'title': '正文', 'ready': True, 'remote': {'materialType': 'report', 'materialId': 'same', 'courseId': 'course', 'version': 1}},
                {'id': 'pending:a', 'ready': False},
            ]},
            {'id': 'b', 'title': '条件', 'resources': []},
        ]},
    }


@pytest.fixture
def reader(catalog):
    def authorize(actor, course_id):
        if actor.user_id != 'alice' or course_id != 'course':
            raise CourseAccessDenied()
    return CourseReader(authorize=authorize,
                        load_manifest=lambda actor, course_id, ref: catalog['manifest'],
                        load_legacy=lambda actor, course_id: deepcopy(catalog['legacy']),
                        load_resource=lambda actor, ref: {'version': 1, 'content': 'old'})


def test_legacy_does_not_invent_completion_rules(reader):
    view = reader.read(Actor(user_id='alice'), 'course')
    assert view.source == 'legacy'
    assert view.manifest_ref is None
    assert view.completion_policy == 'unknown'
    assert view.topics[0].resources[0].required is None
    assert len(view.topics[0].resources) == 1


def test_reordering_keeps_topic_identity(reader, catalog):
    before = reader.read(Actor(user_id='alice'), 'course')
    catalog['legacy']['chapters'].reverse()
    after = reader.read(Actor(user_id='alice'), 'course')
    assert {t.topic_id for t in before.topics} == {t.topic_id for t in after.topics}


def test_denied_before_loading(reader):
    with pytest.raises(CourseAccessDenied):
        reader.read(Actor(user_id='bob'), 'course')


def test_missing_version_never_reads_latest(reader):
    with pytest.raises(ResourceVersionUnavailable):
        reader.read_resource(Actor(user_id='alice'), ResourceRef(course_id='course', material_type='report', material_id='same', version=2))


def test_manifest_maps_preparation_node_and_resource_names(reader, catalog):
    catalog['manifest'] = {'manifest_id': 'cm', 'course_id': 'course', 'version': 1, 'route_version': 1,
        'goal': '学习', 'nodes': [{'node_id': 'stable', 'title': '变量', 'order': 1,
        'objectives': [{'objective_id': 'obj', 'text': '解释变量'}], 'resources': [
        {'resource_id': 'same', 'resource_type': 'report', 'version': 1, 'required': True, 'order': 1, 'objective_ids': ['obj']}]}]}
    view = reader.read(Actor(user_id='alice'), 'course')
    assert view.completion_policy == 'explicit'
    assert view.topics[0].topic_id == 'stable'
    assert view.topics[0].resources[0].resource_ref.material_type == 'report'


def test_requested_manifest_must_not_fall_back_to_legacy(reader):
    from app.self_learning.contracts import ManifestRef
    from app.self_learning.course_reader import ManifestUnavailable
    with pytest.raises(ManifestUnavailable):
        reader.read(Actor(user_id='alice'), 'course', ManifestRef(manifest_id='cm', version=1))
