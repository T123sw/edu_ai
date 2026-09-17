import os
from fastapi import HTTPException
from .context_builder import ContextBuilder
from .repository import SessionConflict, SessionMissing
from .turn_repository import TurnRepository


def configured_turn_repository(session_repository):
    if os.getenv('LEARNING_AGENT_V1_ENABLED', '').lower() not in {'true', '1'}:
        return None
    if session_repository is None:
        raise RuntimeError('Learning Agent requires persistent topic sessions')
    from sqlalchemy import inspect
    if not inspect(session_repository.engine).has_table('learning_agent_outbox'):
        raise RuntimeError('Apply migration 20260917_0026 before enabling learning Agent')
    return TurnRepository(session_repository.engine)


class TurnService:
    def __init__(self, learning, repository):
        self.learning, self.repository = learning, repository

    def public(self, turn):
        value = {k: turn[k] for k in ('turn_id', 'session_id', 'request_id', 'topic_id', 'status', 'stage', 'attempt', 'result', 'error_code')}
        if getattr(self.learning, 'memory', None):
            from sqlalchemy import select
            from sqlalchemy.orm import Session
            from .enrichment_models import LearningCheck, LearningEnrichmentReceipt
            prefix = turn['turn_id'] + ':'
            with Session(self.repository.engine) as db:
                effects = [{'kind': 'understanding_check', 'check_id': row.check_id} for row in db.scalars(select(LearningCheck).where(
                    LearningCheck.owner == turn['owner'], LearningCheck.request_id.startswith(prefix, autoescape=True)))]
                effects.extend({'kind': 'preference', 'field': row.result['field'], 'scope': row.result['scope']} for row in db.scalars(
                    select(LearningEnrichmentReceipt).where(LearningEnrichmentReceipt.owner == turn['owner'], LearningEnrichmentReceipt.operation_id.startswith(prefix, autoescape=True))))
            value['committed_effects'] = effects
        return value

    def accept(self, owner, course, topic, request):
        if not request.question.strip():
            raise HTTPException(422, '请输入问题')
        ContextBuilder(self.learning).authorize(owner, course, topic, request.reading_context.model_dump(mode='json'))
        session = self.learning.sessions.enter(owner, course, topic)
        try:
            from .service import gateway
            from app.services.runtime_config_resolver import runtime_config_resolver
            snapshot = runtime_config_resolver.capture_snapshot(owner) if self.learning.model_factory is gateway else {}
            return self.public(self.repository.accept(owner, session['session_id'], request, {k: v for k, v in snapshot.items() if k == 'llm'}))
        except SessionConflict as exc:
            raise HTTPException(409, str(exc)) from exc

    def get(self, owner, tid):
        try:
            turn = self.repository.get(owner, tid)
        except SessionMissing as exc:
            raise HTTPException(404, '轮次不存在或无权访问') from exc
        ContextBuilder(self.learning).authorize(owner, turn['course_id'], turn['topic_id'], turn['request']['reading_context'])
        return self.public(turn)

    def list_topic(self, owner, course, topic):
        self.learning.sessions._chapter(owner, course, topic)
        session = self.learning.session_repository.find(owner, course, topic)
        if session is None:
            return []
        result = []
        for turn in self.repository.list_topic(owner, session['session_id']):
            try:
                result.append(self.get(owner, turn['turn_id']))
            except HTTPException as exc:
                if exc.status_code not in {404, 409}:
                    raise
                result.append({**self.public(turn), 'result': None, 'context_available': False})
        return result

    def control(self, owner, tid, operation):
        if operation == 'retry':
            self.get(owner, tid)
        else:
            try:
                turn = self.repository.get(owner, tid)
                self.learning.require(turn['course_id'], owner)
            except SessionMissing as exc:
                raise HTTPException(404, '轮次不存在或无权访问') from exc
        try:
            return self.public(self.repository.control(owner, tid, operation))
        except SessionConflict as exc:
            raise HTTPException(409, str(exc)) from exc


def build_learning_runtime():
    if os.getenv('LEARNING_AGENT_V1_ENABLED', '').lower() not in {'true', '1'}:
        return None
    from .service import LearningService
    from .agent_runtime import LearningAgentRuntime
    service = LearningService()
    return LearningAgentRuntime(service, service.turn_repository) if service.turn_repository else None
