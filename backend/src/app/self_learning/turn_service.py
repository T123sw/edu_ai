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
    return TurnRepository(session_repository.engine)


class TurnService:
    def __init__(self, learning, repository):
        self.learning, self.repository = learning, repository

    @staticmethod
    def public(turn):
        return {**{k: turn[k] for k in ('turn_id', 'session_id', 'request_id', 'topic_id', 'status', 'stage', 'attempt', 'result', 'error_code')},
                'preparation_receipts': list((turn.get('checkpoint',{}).get('packet',{}).get('preparation_receipts',{}) or turn.get('checkpoint',{}).get('recovered_preparations',{})).values())}

    def accept(self, owner, course, topic, request):
        from .rollout import require_scope
        require_scope(owner,course)
        if not request.question.strip():
            raise HTTPException(422, '请输入问题')
        ContextBuilder(self.learning).authorize(owner, course, topic, request.reading_context.model_dump(mode='json'))
        session = self.learning.sessions.enter(owner, course, topic)
        try:
            return self.public(self.repository.accept(owner, session['session_id'], request))
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
        session = self.learning.sessions.enter(owner, course, topic)
        return [self.get(owner, t['turn_id']) for t in self.repository.list_topic(owner, session['session_id'])]

    def control(self, owner, tid, operation):
        self.get(owner, tid)
        try:
            return self.public(self.repository.control(owner, tid, operation))
        except SessionConflict as exc:
            raise HTTPException(409, str(exc)) from exc


def build_learning_runtime():
    from .service import LearningService
    from .agent_runtime import LearningAgentRuntime
    service = LearningService()
    return LearningAgentRuntime(service, service.turn_repository) if service.turn_repository else None
