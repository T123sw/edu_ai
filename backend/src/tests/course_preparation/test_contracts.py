from copy import deepcopy
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.course_preparation.schemas import PreparationRequest, request_digest
from app.course_preparation.manifest import CourseManifest


def request_payload(**changes):
    return dict(request_id=str(uuid4()), operation='create_course', goal='学习递归', **changes)


def manifest_payload():
    return {
        'manifest_id': 'manifest-1', 'course_id': 'course-1', 'version': 1,
        'route_version': 1, 'goal': '理解递归', 'audience': '入门',
        'estimated_minutes': 20, 'quality_report_id': 'review-1',
        'created_by_preparation_id': 'prep-1',
        'nodes': [{
            'node_id': 'node-1', 'title': '终止条件', 'order': 1,
            'estimated_minutes': 20,
            'objectives': [{'objective_id': 'obj-1', 'text': '识别终止条件'}],
            'resources': [{
                'resource_id': 'resource-1', 'resource_type': 'report', 'version': 1,
                'content_sha256': 'a' * 64, 'purpose': '讲解', 'order': 1,
                'objective_ids': ['obj-1'], 'source_refs': ['evidence-1'],
            }],
            'checks': [{
                'check_id': 'check-1', 'objective_ids': ['obj-1'],
                'mode': 'self_check', 'resource_id': 'resource-1',
                'resource_version': 1, 'locator': {'section_id': 'practice'},
            }],
        }],
    }


@pytest.mark.parametrize('field,value', [
    ('owner_user_id', 'bob'), ('execution_mode', 'course_preparation'),
    ('space', 'public'), ('goal', '   '), ('schema_version', 2),
])
def test_untrusted_or_invalid_input_rejected(field, value):
    payload = request_payload()
    payload[field] = value
    with pytest.raises(ValidationError):
        PreparationRequest.model_validate(payload)


def test_source_defaults_and_canonical_request_hash():
    payload = request_payload()
    implicit = PreparationRequest.model_validate(payload)
    explicit = PreparationRequest.model_validate({**payload, 'source_policy': {'mode': 'open'}})
    assert implicit.source_policy.mode == 'open'
    assert request_digest(implicit) == request_digest(explicit)
    upload = {'document_id': 'doc-1', 'version': 1, 'usage': 'primary'}
    with_upload = PreparationRequest.model_validate({**payload, 'uploads': [upload]})
    assert with_upload.source_policy.mode == 'uploads_preferred'
    assert request_digest(with_upload) != request_digest(implicit)
    with pytest.raises(ValidationError):
        PreparationRequest.model_validate({**payload, 'source_policy': {'mode': 'uploaded_only'}})
    with pytest.raises(ValidationError):
        PreparationRequest.model_validate({**payload, 'uploads': [upload, upload]})


@pytest.mark.parametrize('operation,target,changes,valid', [
    ('create_course', {'course_id': 'c', 'base_manifest_version': 1}, None, False),
    ('supplement_node', {'course_id': 'c', 'node_id': 'n', 'base_manifest_version': 1}, None, True),
    ('supplement_node', {'course_id': 'c', 'base_manifest_version': 1}, None, False),
    ('revise_resource', {'course_id': 'c', 'node_id': 'n', 'base_manifest_version': 1}, None, False),
    ('revise_resource', {'course_id': 'c', 'node_id': 'n', 'base_manifest_version': 1,
                         'resource_id': 'r', 'base_resource_version': 2}, None, True),
    ('adjust_course', {'course_id': 'c', 'base_manifest_version': 1,
                       'base_route_version': 1}, ['增加实践内容'], True),
    ('adjust_course', {'course_id': 'c', 'base_manifest_version': 1,
                       'base_route_version': 1}, None, False),
])
def test_operation_scope(operation, target, changes, valid):
    payload = request_payload()
    payload.update(operation=operation, target=target)
    if changes is not None:
        payload['requested_changes'] = changes
    if valid:
        assert PreparationRequest.model_validate(payload).operation == operation
    else:
        with pytest.raises(ValidationError):
            PreparationRequest.model_validate(payload)


def test_valid_manifest_roundtrip():
    manifest = CourseManifest.model_validate(manifest_payload())
    assert CourseManifest.model_validate_json(manifest.model_dump_json()) == manifest


@pytest.mark.parametrize('mutation', [
    lambda m: m['nodes'].append(deepcopy(m['nodes'][0])),
    lambda m: m['nodes'][0].update(prerequisite_node_ids=['missing']),
    lambda m: m['nodes'][0].update(prerequisite_node_ids=['node-1']),
    lambda m: m['nodes'][0].update(resources=[]),
    lambda m: m['nodes'][0].update(checks=[]),
    lambda m: m['nodes'][0]['resources'][0].update(objective_ids=['unknown']),
    lambda m: m['nodes'][0]['resources'][0].update(required=False),
    lambda m: m['nodes'][0]['checks'][0].update(resource_version=2),
    lambda m: m['nodes'][0]['checks'][0].update(locator={}),
    lambda m: m['nodes'][0]['resources'][0].update(content_sha256='fake'),
])
def test_invalid_delivery_structure_is_rejected(mutation):
    payload = manifest_payload()
    mutation(payload)
    with pytest.raises(ValidationError):
        CourseManifest.model_validate(payload)


def test_prerequisite_order_and_stable_ids():
    payload = manifest_payload()
    second = deepcopy(payload['nodes'][0])
    second.update(node_id='node-2', order=2, prerequisite_node_ids=['node-1'])
    second['objectives'][0]['objective_id'] = 'obj-2'
    second['resources'][0].update(resource_id='resource-2', objective_ids=['obj-2'])
    second['checks'][0].update(check_id='check-2', resource_id='resource-2', objective_ids=['obj-2'])
    payload['nodes'].append(second)
    assert len(CourseManifest.model_validate(payload).nodes) == 2
    payload['nodes'][0]['prerequisite_node_ids'] = ['node-2']
    with pytest.raises(ValidationError):
        CourseManifest.model_validate(payload)
