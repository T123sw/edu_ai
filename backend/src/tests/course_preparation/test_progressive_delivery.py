from copy import deepcopy

import pytest
from sqlalchemy import select, func, event
from sqlalchemy.orm import Session

from app.database.models import (PreparationArtifact, PreparedManifestVersion, PreparedCoursePointer,
    PreparationDeliveryEvent, Course, Material, PreparationExecution, CourseMembership)
from app.course_preparation.progressive_delivery import ProgressiveDelivery
from app.course_preparation.quality import candidate_manifest, check_digest, RULE_VERSION
from app.course_preparation.tool_registry import digest
from app.course_preparation.lifecycle_repository import StaleLease
from app.self_learning.course_reader import CourseReader
from tests.course_preparation.test_delivery import ready
from tests.course_preparation.test_generation_adapter import generation
from tests.test_self_learning import service


@pytest.fixture
def available(ready):
    from app.chat.harness.reviewed_report import CRITERIA, digest as report_digest
    repo, context, delivery = ready
    cp = deepcopy(context.checkpoint)
    checked = cp['artifacts'][0]
    artifact = checked['content']
    artifact['generation_state']['report_review'] = {'decision': 'pass', 'method': 'model_review',
        'content_sha256': report_digest(artifact['content']),
        'checks': [{'criterion': c, 'passed': True} for c in CRITERIA]}
    checked['content_digest'] = digest(artifact)
    cp['resource_specs'] = [checked['spec']]
    with Session(repo.engine) as session, session.begin():
        row = session.get(PreparationArtifact, checked['artifact_id'])
        row.content, row.content_digest = artifact, checked['content_digest']
    repo.checkpoint(context, cp)
    context = context.model_copy(update={'checkpoint': cp})
    return repo, context, delivery, ProgressiveDelivery(repo)


def test_partial_delivery_survives_other_resource_failure_and_manual_retry(available):
    repo, context, delivery, publisher = available
    cp = deepcopy(context.checkpoint)
    cp['resource_specs'].append({**cp['resource_specs'][0], 'resource_type': 'quiz'})
    repo.checkpoint(context, cp)
    publisher.publish(context, cp)
    public = repo.get_public('alice', context.preparation_id)
    assert public['status'] == 'running'
    result = public['result_ref']
    assert result['course_available'] and not result['course_ready']
    assert (result['available_resources'], result['planned_resources']) == (1, 2)
    manifest = delivery.read('alice', result['course_id'])
    assert manifest['delivery_state'] == 'partial'
    assert manifest['nodes'][0]['pending_resource_types'] == ['quiz']
    assert CourseReader._manifest(manifest).topics[0].completion_policy == 'unknown'
    repo.checkpoint(context, cp)
    repo.fail(context, 'RESOURCE_REPAIR_FORMAT_INVALID')
    failed = repo.get_public('alice', context.preparation_id)
    assert failed['result_ref'] == result
    assert '已有资料可以学习' in failed['failure']['title']
    retried = repo.retry('alice', context.preparation_id)
    assert retried['result_ref'] == result
    with Session(repo.engine) as session:
        assert session.scalar(select(func.count()).select_from(Material)) == 1
        assert session.scalar(select(func.count()).select_from(PreparationDeliveryEvent)) == 0


def test_repeated_publication_is_idempotent_then_final_commit_advances_same_course(available):
    repo, context, delivery, publisher = available
    cp = deepcopy(context.checkpoint)
    publisher.publish(context, cp)
    first = repo.get_public('alice', context.preparation_id)['result_ref']
    publisher.publish(context, cp)
    assert repo.get_public('alice', context.preparation_id)['result_ref'] == first
    cp['quality'] = {'decision': 'pass', 'input_digest': check_digest(cp), 'rule_version': RULE_VERSION}
    request = repo.get(owner_user_id='alice', preparation_id=context.preparation_id).request
    cp['candidate_manifest'] = candidate_manifest(context, cp, request).model_dump(mode='json')
    repo.checkpoint(context, cp)
    context = context.model_copy(update={'checkpoint': cp})
    final = delivery.commit(context).result_ref
    assert final['course_ready'] and final['manifest_version'] == first['manifest_version'] + 1
    assert final['course_id'] == first['course_id']
    assert delivery.read('alice', final['course_id'])['delivery_state'] == 'complete'
    with Session(repo.engine) as session:
        assert session.scalar(select(func.count()).select_from(Course)) == 1
        assert session.scalar(select(func.count()).select_from(Material)) == 1
        assert session.scalar(select(func.count()).select_from(PreparationDeliveryEvent)) == 1


def test_recovery_publishes_saved_resources_without_retry_or_model_calls(available):
    repo, context, delivery, publisher = available
    repo.fail(context, 'PREPARATION_CONTENT_CONTRACT')
    public = publisher.recover_saved('alice', context.preparation_id)
    assert public['attempt_no'] == 1 and public['status'] == 'failed'
    assert public['result_ref']['available_resources'] == 1
    assert len(delivery.read('alice', public['result_ref']['course_id'])['nodes'][0]['resources']) == 1
    assert publisher.recover_saved('alice', context.preparation_id)['result_ref'] == public['result_ref']
    with pytest.raises(Exception):
        publisher.recover_saved('bob', context.preparation_id)


def test_partial_publication_rolls_back_membership_material_and_pointer_together(available):
    repo, context, _, publisher = available
    def reject(*_):
        raise RuntimeError('test manifest write failure')
    event.listen(PreparedManifestVersion, 'before_insert', reject)
    try:
        with pytest.raises(RuntimeError, match='test manifest'):
            publisher.publish(context, dict(context.checkpoint))
    finally:
        event.remove(PreparedManifestVersion, 'before_insert', reject)
    assert repo.get_public('alice', context.preparation_id)['result_ref'] is None
    with Session(repo.engine) as session:
        for model in (Course, Material, CourseMembership, PreparedCoursePointer):
            assert session.scalar(select(func.count()).select_from(model)) == 0


@pytest.mark.parametrize('mutation', ['content', 'receipt', 'lease', 'membership'])
def test_unusable_drafts_and_revoked_access_cannot_be_published(available, mutation):
    repo, context, _, publisher = available
    cp = deepcopy(context.checkpoint)
    if mutation == 'membership':
        publisher.publish(context, cp)
    with Session(repo.engine) as session, session.begin():
        if mutation in ('content', 'receipt'):
            row = session.get(PreparationArtifact, cp['artifacts'][0]['artifact_id'])
            row.content = {**row.content, 'content': 'tampered'} if mutation == 'content' else {**row.content, 'generation_state': {}}
            if mutation == 'receipt':
                row.content_digest = digest(row.content)
        elif mutation == 'lease':
            session.get(PreparationExecution, (context.preparation_id, 1)).lease_token = 'replaced'
        else:
            session.delete(session.get(CourseMembership, (cp['partial_delivery']['course_id'], 'alice')))
            cp['plan'] = {**cp['plan'], 'title': 'new title'}  # Force a new publication.
    if mutation in ('content', 'receipt'):
        publisher.publish(context, cp)
        assert repo.get_public('alice', context.preparation_id)['result_ref'] is None
    else:
        with pytest.raises(StaleLease if mutation == 'lease' else PermissionError):
            publisher.publish(context, cp)


def test_complete_manifest_cannot_claim_unfinished_node_is_ready(available):
    from app.course_preparation.manifest import CourseManifest
    repo, context, delivery, publisher = available
    cp = deepcopy(context.checkpoint)
    cp['resource_specs'].append({**cp['resource_specs'][0], 'resource_type': 'quiz'})
    publisher.publish(context, cp)
    manifest = delivery.read('alice', repo.get_public('alice', context.preparation_id)['result_ref']['course_id'])
    with pytest.raises(ValueError, match='unfinished nodes'):
        CourseManifest.model_validate({**manifest, 'delivery_state': 'complete'})


def test_path_publishes_before_resources_then_opens_completed_node(available):
    repo, context, delivery, publisher = available
    cp = deepcopy(context.checkpoint)
    artifact_id = cp['artifacts'][0]['artifact_id']
    second = {**cp['plan']['nodes'][0], 'node_key': 'later', 'title': '后续知识点'}
    cp['plan']['nodes'].append(second)
    cp['node_evidence']['later'] = cp['node_evidence']['tools']
    cp['resource_specs'].append({**cp['resource_specs'][0], 'node_id': 'later', 'objective_ids': ['later:o1']})
    with Session(repo.engine) as session, session.begin():
        session.get(PreparationArtifact, artifact_id).status = 'pending'
    publisher.publish(context, cp)
    first = repo.get_public('alice', context.preparation_id)['result_ref']
    assert first['path_available'] and not first['course_available']
    manifest = delivery.read('alice', first['course_id'])
    assert [n['generation_status'] for n in manifest['nodes']] == ['queued', 'queued']
    assert all(not n['resources'] for n in manifest['nodes'])
    with Session(repo.engine) as session, session.begin():
        session.get(PreparationArtifact, artifact_id).status = 'running'
    publisher.publish(context, cp)
    assert delivery.read('alice', first['course_id'])['nodes'][0]['generation_status'] == 'generating'
    with Session(repo.engine) as session, session.begin():
        session.get(PreparationArtifact, artifact_id).status = 'draft'
    publisher.publish(context, cp)
    final = repo.get_public('alice', context.preparation_id)['result_ref']
    assert final['course_id'] == first['course_id'] and final['manifest_version'] > first['manifest_version']
    assert final['available_resources'] == 1 and not final['course_ready']
    manifest = delivery.read('alice', first['course_id'])
    assert [n['generation_status'] for n in manifest['nodes']] == ['ready', 'queued']
    assert manifest['nodes'][0]['delivery_state'] == 'ready'
    with Session(repo.engine) as session:
        assert session.scalar(select(func.count()).select_from(Material)) == 1


def test_memory_context_rebuild_preserves_published_course_identity(available):
    repo, context, _, publisher = available
    cp = deepcopy(context.checkpoint)
    publisher.publish(context, cp)
    before = repo.get_public('alice', context.preparation_id)['result_ref']
    repo.restart_for_memory(context, 'alice')
    current = repo.claim('after-memory-change', preparation_id=context.preparation_id)
    assert current.stage == 'normalize'
    assert current.checkpoint['partial_delivery']['manifest_version'] == before['manifest_version']
    assert repo.get_public('alice', context.preparation_id)['result_ref'] == before


def test_learning_room_exposes_path_and_stopped_nodes_without_resources(available, service):
    from app.self_learning.prepared_courses import PreparedCourses
    repo, context, _, publisher = available
    cp = deepcopy(context.checkpoint)
    with Session(repo.engine) as session, session.begin():
        session.get(PreparationArtifact, cp['artifacts'][0]['artifact_id']).status = 'pending'
    publisher.publish(context, cp)
    service.prepared_courses = PreparedCourses(repo.engine)
    course = repo.get_public('alice', context.preparation_id)['result_ref']['course_id']
    room = service.room(course, 'alice', include_progress=False)
    assert room['chapters'][0]['generationState'] == 'queued'
    assert room['chapters'][0]['resources'][0]['ready'] is False
    assert room['preparationDelivery']['status'] == 'running'
    repo.fail(context, 'PROVIDER_TIMEOUT')
    room = service.room(course, 'alice', include_progress=False)
    assert room['chapters'][0]['generationState'] == 'stopped'
    assert room['preparationDelivery']['status'] == 'failed'
    assert service.prepared_courses.preparation_status('bob', context.preparation_id) is None


def test_cancel_preserves_delivered_resources_and_course_entry(available):
    repo, context, delivery, publisher = available
    cp = deepcopy(context.checkpoint)
    cp['resource_specs'].append({**cp['resource_specs'][0], 'resource_type': 'quiz'})
    publisher.publish(context, cp)
    before = repo.get_public('alice', context.preparation_id)['result_ref']
    canceled = repo.cancel('alice', context.preparation_id, expected_attempt_no=1)
    assert canceled['status'] == 'canceled'
    assert canceled['result_ref'] == before
    assert delivery.read('alice', before['course_id'])['nodes'][0]['resources']
    with Session(repo.engine) as session:
        assert session.scalar(select(func.count()).select_from(Material)) == 1


def test_room_keeps_all_planned_slots_when_one_resource_is_already_available(available, service):
    from app.self_learning.prepared_courses import PreparedCourses
    repo, context, _, publisher = available
    cp = deepcopy(context.checkpoint)
    cp['resource_specs'].extend([{**cp['resource_specs'][0], 'resource_type': kind} for kind in ('quiz', 'classroom')])
    publisher.publish(context, cp)
    service.prepared_courses = PreparedCourses(repo.engine)
    course = repo.get_public('alice', context.preparation_id)['result_ref']['course_id']
    resources = service.room(course, 'alice', include_progress=False)['chapters'][0]['resources']
    assert [r['kind'] for r in resources] == ['video', 'report', 'quiz']
    assert [r['ready'] for r in resources] == [False, True, False]
    assert resources[0]['id'].endswith(':video') and resources[2]['id'].endswith(':quiz')
