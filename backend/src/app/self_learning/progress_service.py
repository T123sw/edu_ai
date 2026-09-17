"""Authorized facts and deterministic projections; no model calls."""
from functools import lru_cache
import os
from fastapi import HTTPException
from sqlalchemy import create_engine
from .contracts import Actor, LearningFacts
from .course_reader import CourseReader, ManifestUnavailable
from .progress_repository import ProgressRepository, ProgressConflict
from .projections import project_topic, next_actions


@lru_cache(maxsize=4)
def _repository(url):
    if not url.startswith(('postgresql:', 'postgresql+')):
        raise RuntimeError('Learning progress requires PostgreSQL')
    return ProgressRepository(create_engine(url, pool_pre_ping=True))


def configured_progress_repository():
    from .rollout import scoped_enabled
    return _repository(os.getenv('DATABASE_URL', '').strip()) if os.getenv('LEARNING_PROGRESS_V1_ENABLED', '').lower() in {'1', 'true'} or scoped_enabled() else None


class ProgressService:
    def __init__(self, reader, repository):
        self.reader, self.repository = reader, repository

    @staticmethod
    def project(view, snapshot):
        from .contracts import ResourceRef
        valid_refs = {r.resource_ref.key for topic in view.topics for r in topic.resources}
        evidence = snapshot.get('check_evidence', [])
        activities = [e['activity_id'] for e in evidence if e.get('activity_id') and e.get('resource_ref') and ResourceRef.model_validate(e['resource_ref']).key in valid_refs]
        facts = LearningFacts(**{k: snapshot[k] for k in ('resources', 'self_assessments', 'facts_revision')}, check_evidence=evidence, completed_activity_ids=activities)
        return {**snapshot, 'manifest_ref': view.manifest_ref.model_dump(mode='json') if view.manifest_ref else None, 'topics': [project_topic(t, facts).model_dump(mode='json') for t in view.topics],
                'next_actions': {t.topic_id: [a.model_dump(mode='json') for a in next_actions(view, facts, t.topic_id)] for t in view.topics}}

    def read(self, actor, course_id):
        view = self.reader.read(actor, course_id)
        return self.project(view, self.repository.read(actor.user_id, course_id))

    def record(self, actor, course_id, topic_id, event):
        # Authorization, current manifest and resource version checks precede replay.
        try:
            view = self.reader.read(actor, course_id, event.manifest_ref)
        except ManifestUnavailable as exc:
            raise HTTPException(409, '课程路线版本已变化，请刷新后重试') from exc
        topic = next((t for t in view.topics if t.topic_id == topic_id), None)
        if topic is None:
            raise HTTPException(404, '知识点不存在或无权访问')
        if event.resource_ref is not None:
            if event.resource_ref not in [r.resource_ref for r in topic.resources]:
                raise HTTPException(409, '学习资料或版本已变化，请刷新后重新操作')
            self.reader.read_resource(actor, event.resource_ref)
        if event.payload.get('source_message_id'):
            # Message-derived self assessments are introduced with P4 provenance validation.
            raise HTTPException(422, '当前仅支持界面直接自评')
        try:
            return self.repository.record(actor.user_id, course_id, topic_id, event,
                                          lambda snapshot: self.project(view, snapshot))
        except ProgressConflict as exc:
            raise HTTPException(409, exc.detail) from exc


def for_learning_service(learning, repository):
    def resource(actor, ref):
        material = learning.material(ref.course_id, ref.material_type, ref.material_id, actor.user_id)
        if material.get('version') != ref.version:
            raise HTTPException(409, '资料版本已变化，请刷新后重试')
        return material
    reader = CourseReader(authorize=lambda actor, course: learning.require(course, actor.user_id),
        load_manifest=lambda *_: None,
        load_legacy=lambda actor, course: learning.room(course, actor.user_id, include_progress=False),
        load_resource=resource)
    return ProgressService(reader, repository)
