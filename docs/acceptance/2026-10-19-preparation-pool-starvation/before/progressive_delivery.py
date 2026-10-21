"""Publish independently usable resources without claiming whole-course completion."""
from types import SimpleNamespace

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.chat.memory.lifecycle import MemoryLifecycle, lock_epoch
from app.database.models import (
    Course, CourseMembership, User, PreparationArtifact as Artifact,
    PreparedCoursePointer as Pointer, PreparedManifestVersion as Version,
    CoursePreparationRecord as Prep, CoursePreparationAttemptRecord as Attempt,
    PreparationExecution as Run,
)
from app.persistence.postgres_material_repository import PostgresMaterialRepository
from .artifact_store import ArtifactStore
from .lifecycle_repository import RevisionConflict
from .quality import candidate_manifest
from .resource_alignment import validate_artifact
from .schemas import PreparationRequest
from .tool_registry import digest


class ProgressiveDelivery:
    def __init__(self, repository):
        self.repository = repository
        self.materials = PostgresMaterialRepository(repository.engine)

    def publish(self, context, checkpoint):
        if not checkpoint.get('resource_specs'):
            return
        with Session(self.repository.engine) as session, session.begin():
            lock_epoch(session, checkpoint['memory_subject'])
            prep, attempt, run, _ = self.repository._locked(session, context)
            self._publish(session, prep, attempt, run, checkpoint)

    def recover_saved(self, owner, preparation_id):
        """Explicit recovery for a stopped task; never enqueue or regenerate anything."""
        with Session(self.repository.engine) as session, session.begin():
            prep = self.repository._owner(session, owner, preparation_id)
            run = session.get(Run, (preparation_id, prep.current_attempt_no))
            lock_epoch(session, run.checkpoint['memory_subject'])
            prep = session.scalar(select(Prep).where(Prep.preparation_id == preparation_id)
                                  .with_for_update().execution_options(populate_existing=True))
            attempt = session.get(Attempt, (preparation_id, prep.current_attempt_no))
            run = session.get(Run, (preparation_id, prep.current_attempt_no))
            if attempt.status not in ('failed', 'canceled'):
                raise ValueError('ONLY_STOPPED_PREPARATION_CAN_RECOVER_SAVED_RESOURCES')
            self.repository.authorizer.authorize(owner, PreparationRequest.model_validate(prep.request_payload))
            self._publish(session, prep, attempt, run, dict(run.checkpoint))
        return self.repository.get_public(owner, preparation_id)

    def _publish(self, session, prep, attempt, run, checkpoint):
        request = PreparationRequest.model_validate(prep.request_payload)
        # Edits to an existing course keep their original atomic revision contract.
        if request.operation != 'create_course':
            return
        MemoryLifecycle.validate_refs_in_session(session, checkpoint['memory_subject'], checkpoint['memory_refs'])
        actor = session.get(User, prep.owner_user_id)
        if actor is None or actor.is_disabled or actor.username != checkpoint['memory_subject']:
            raise PermissionError('OWNER_UNAVAILABLE')
        specs = {digest(s): s for s in checkpoint['resource_specs']}
        rows = session.scalars(select(Artifact).where(
            Artifact.preparation_id == prep.preparation_id, Artifact.owner_user_id == prep.owner_user_id,
            Artifact.spec_digest.in_(specs)).order_by(Artifact.artifact_id).with_for_update()).all()
        artifacts, excluded = [], []
        for row in rows:
            if row.status != 'draft':
                continue
            checked = {**ArtifactStore.view(row), 'content': row.content}
            MemoryLifecycle.validate_refs_in_session(session, row.spec['memory_subject'], row.spec['memory_refs'])
            try:
                if (row.spec != specs[row.spec_digest] or digest(row.spec) != row.spec_digest
                        or row.content is None or digest(row.content) != row.content_digest):
                    raise ValueError('ARTIFACT_CHANGED_BEFORE_DELIVERY')
                validate_artifact(checked)
                from .adapters.generation import verify_draft
                verify_draft(checked)
            except ValueError:
                # A corrupt/unusable resource cannot suppress other independent resources.
                excluded.append(row.artifact_id)
                continue
            artifacts.append(checked)
        previous = run.checkpoint.get('partial_delivery', {})
        checkpoint['partial_delivery'] = previous
        # A validated learning path is visible before its first resource finishes.
        # Corrupt drafts remain excluded and cannot masquerade as delivered content.
        if not artifacts and excluded:
            return
        states = {row.spec_digest: 'failed' if row.artifact_id in excluded else row.status for row in rows}
        checkpoint['resource_generation_states'] = states
        signature = digest({'resources': [(a['artifact_id'], a['content_digest']) for a in artifacts],
                            'specs': list(specs), 'plan': checkpoint['plan'], 'states': states})
        if signature == previous.get('signature'):
            return
        context = SimpleNamespace(owner_user_id=prep.owner_user_id, preparation_id=prep.preparation_id)
        manifest = candidate_manifest(context, {**checkpoint, 'artifacts': artifacts}, request, partial=True)
        pointer = session.scalar(select(Pointer).where(Pointer.owner_user_id == prep.owner_user_id,
            Pointer.course_id == manifest.course_id).with_for_update())
        expected = previous.get('manifest_version', 0)
        if (pointer.version if pointer else 0) != expected:
            raise RevisionConflict('MANIFEST_BASE_CHANGED')
        if pointer:
            prior = session.get(Version, (prep.owner_user_id, manifest.course_id, pointer.version))
            if prior is None or prior.preparation_id != prep.preparation_id or prior.payload.get('delivery_state') != 'partial':
                raise RevisionConflict('MANIFEST_BASE_CHANGED')
        now = self.repository.clock().isoformat()
        course = session.get(Course, manifest.course_id)
        if course is None:
            info = {'id': manifest.course_id, 'title': checkpoint['plan']['title'], 'description': manifest.goal,
                    'created_by': actor.username, 'created_at': now, 'updated_at': now,
                    'self_learning': True, 'prepared_course': True}
            session.add(Course(course_id=manifest.course_id, title=info['title'], description=manifest.goal,
                               created_by=prep.owner_user_id, raw_payload=info))
            session.flush()
            session.add(CourseMembership(course_id=manifest.course_id, user_id=prep.owner_user_id,
                                         role='owner', added_by=prep.owner_user_id))
        elif session.get(CourseMembership, (manifest.course_id, prep.owner_user_id)) is None:
            raise PermissionError('COURSE_MEMBERSHIP_REVOKED')
        for checked in artifacts:
            artifact, spec = checked['content'], checked['spec']
            body = artifact['content']
            payload = {'course_id': manifest.course_id, 'material_type': checked['resource_type'],
                'material_id': checked['resource_id'], 'title': artifact['title'], 'content': body,
                'generation_state': artifact['generation_state'], 'version': checked['resource_version'],
                'content_hash': checked['content_digest'], 'visibility': 'private', 'origin_type': 'personal',
                'owner_user_id': actor.username, 'created_by': actor.username,
                'scope_type': 'knowledge_point', 'scope_id': spec['node_id'],
                'created_at': now, 'updated_at': now, 'learning_course_resource': True,
                'preparation_id': prep.preparation_id, 'preparation_artifact': artifact, 'status': 'ready'}
            if checked['resource_type'] == 'classroom':
                payload.update(body)
            if checked['resource_type'] == 'quiz':
                payload['questions'] = body['questions']
            self.materials.upsert(payload, session=session)
            session.flush()
        payload = manifest.model_dump(mode='json')
        session.add(Version(owner_user_id=prep.owner_user_id, course_id=manifest.course_id, version=manifest.version,
            manifest_id=manifest.manifest_id, preparation_id=prep.preparation_id, payload=payload, content_digest=digest(payload)))
        if pointer is None:
            session.add(Pointer(owner_user_id=prep.owner_user_id, course_id=manifest.course_id, version=manifest.version))
        else:
            pointer.version = manifest.version
        result = {'course_id': manifest.course_id, 'manifest_id': manifest.manifest_id,
                  'manifest_version': manifest.version, 'course_ready': False, 'course_available': bool(artifacts),
                  'path_available': True,
                  'available_resources': len(artifacts), 'planned_resources': len(specs)}
        checkpoint['partial_delivery'] = {**result, 'signature': signature, 'excluded_artifact_ids': excluded}
        run.checkpoint = {**run.checkpoint, 'partial_delivery': checkpoint['partial_delivery']}
        run.result_ref = result
        self.repository._event(session, prep, attempt, 'child_updated', {'kind': 'resources_available', **result})
