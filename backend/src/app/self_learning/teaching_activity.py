"""Bind actual attempts to tutoring, without making model text a learning fact."""
import time
from uuid import NAMESPACE_URL, uuid5
from fastapi import HTTPException
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session
from .enrichment_models import LearningCheck, LearningCheckAttempt
from .teaching_activity_models import LearningTeachingActivity as Activity, LearningTeachingFeedback as Feedback, TABLES
from .turn_contracts import AnswerRequest, PracticeContext
from .progress_repository import digest


class TeachingActivityService:
    def __init__(self, checks):
        self.checks, self.learning, self.engine = checks, checks.learning, checks.engine
        self.available = all(inspect(self.engine).has_table(name) for name in TABLES)

    def require_available(self):
        if not self.available or not self.learning.turns:
            raise HTTPException(503, '习题辅导流程尚未启用，请先完成教学活动迁移和答疑服务配置')

    @staticmethod
    def question_index(row, ref, index):
        # Old material checks already have a deterministic version + position key.
        return (row.source.get('question_index') == index or row.request_id == 'material:' +
                digest([ref['course_id'], ref['material_id'], ref['version'], index]))

    def resolve(self, owner, course, topic, reading):
        raw = reading.get('practice')
        if not raw:
            return None
        context = PracticeContext.model_validate(raw)
        with Session(self.engine) as db:
            row = self.checks.owned(db, owner, context.check_id)
            ref = reading['resource_ref']
            if row.course_id != course or row.topic_id != topic or row.source.get('resource_ref') != ref:
                raise HTTPException(404, '作答不属于当前知识点或资料版本')
            locator = reading.get('locator') or {}
            if locator.get('kind') == 'quiz' and not self.question_index(row, ref, locator['question_index']):
                raise HTTPException(409, '作答与当前题目不一致，请重新选择题目')
            result = {'check_id': row.check_id, 'question': self.checks.public(row)['public_question'],
                      'objective_ids': row.objective_ids, 'answer_status': 'not_provided'}
            if context.attempt_id:
                attempt = db.get(LearningCheckAttempt, context.attempt_id)
                if not attempt or attempt.owner != owner or attempt.check_id != row.check_id:
                    raise HTTPException(404, '作答记录不存在或不属于这道题')
                p = attempt.payload
                result.update(answer_status='submitted', attempt={key: p.get(key) for key in
                    ('attempt_id', 'status', 'option_ids', 'text', 'correct', 'evaluator', 'feedback')})
            elif context.draft is not None:
                draft = context.draft.model_dump()
                options = {o['id'] for o in row.question['options']}
                if (len(set(draft['option_ids'])) != len(draft['option_ids']) or
                    not set(draft['option_ids']) <= options or
                    (row.question['form'] == 'choice' and draft['text']) or
                    (row.question['form'] == 'short_answer' and draft['option_ids'])):
                    raise HTTPException(422, '草稿与题型不一致')
                result.update(answer_status='unsubmitted_draft', draft=draft)
            if self.available:
                activity = db.get(Activity, row.check_id)
                result['coaching_enabled'] = bool(activity and activity.enabled)
            return result

    def view(self, owner, check_id):
        if not self.available or not self.learning.turns:
            return None
        with Session(self.engine) as db:
            check = self.checks.owned(db, owner, check_id, allow_saved=True)
            return self._views(db, owner, [check])[check_id]

    def _views(self, db, owner, checks):
        """Project already-authorized snapshots in one batch, within this request only."""
        if not self.available or not self.learning.turns:
            return {check.check_id: None for check in checks}
        ids = [check.check_id for check in checks]
        activities = {row.check_id: row for row in db.scalars(select(Activity).where(
            Activity.owner == owner, Activity.check_id.in_(ids)))}
        latest, events = {}, {}
        for row in db.scalars(select(LearningCheckAttempt).where(LearningCheckAttempt.owner == owner,
                LearningCheckAttempt.check_id.in_(ids)).order_by(LearningCheckAttempt.created_at.desc())):
            latest.setdefault(row.check_id, row)
        for row in db.scalars(select(Feedback).where(Feedback.owner == owner,
                Feedback.check_id.in_(ids)).order_by(Feedback.created_at.desc())):
            events.setdefault(row.check_id, row)
        result = {}
        for check in checks:
            row, attempt, event = activities.get(check.check_id), latest.get(check.check_id), events.get(check.check_id)
            feedback = None
            if event:
                feedback = {'attempt_id': event.attempt_id, 'status': event.status, 'turn_id': event.turn_id, 'error': event.error}
                if event.turn_id:
                    turn = self.learning.turn_repository.get(owner, event.turn_id)
                    feedback.update(status=turn['status'], error=turn['error_code'])
            stage = 'waiting_answer'
            if attempt:
                stage = 'skipped' if attempt.payload['status'] == 'skipped' else 'answer_saved'
                if attempt.payload['status'] in ('pending_evaluation', 'evaluation_failed'):
                    stage = attempt.payload['status']
                elif feedback and feedback['attempt_id'] == attempt.attempt_id:
                    stage = 'feedback_ready' if feedback['status'] == 'succeeded' else 'feedback_failed' if feedback['status'] in ('failed', 'canceled') else 'feedback_pending'
            result[check.check_id] = {'enabled': bool(row and row.enabled), 'revision': row.revision if row else 0, 'feedback': feedback,
                    'stage': stage, 'check_id': check.check_id, 'topic_id': check.topic_id,
                    'source_ref': check.source.get('resource_ref'), 'latest_attempt_id': attempt.attempt_id if attempt else None}
        return result

    def configure(self, owner, check_id, enabled, expected_revision):
        self.require_available()
        with self.checks._write('learning-checks:' + owner) as db:
            check = self.checks.owned(db, owner, check_id)
            if not check.source.get('resource_ref'):
                raise HTTPException(409, '这道题没有可追溯资料，暂不能开启连续辅导')
            row = db.get(Activity, check_id)
            current = row.revision if row else 0
            if current != expected_revision:
                # Replaying the same update is harmless; stale opposite updates fail.
                if not row or row.enabled != enabled or current != expected_revision + 1:
                    raise HTTPException(409, '辅导设置已变化，请刷新后重试')
            elif not row:
                db.add(Activity(check_id=check_id, owner=owner, enabled=enabled, revision=1, updated_at=time.time()))
            elif row.enabled != enabled:
                row.enabled, row.revision, row.updated_at = enabled, current + 1, time.time()
        return self.view(owner, check_id)

    def stage_feedback(self, db, check, result):
        """Called in the same transaction that saves the graded attempt."""
        if not self.available or result['status'] != 'graded' or not result.get('teaching_requested') or not self.learning.turns:
            return
        activity = db.get(Activity, check.check_id)
        if not activity or not activity.enabled or db.get(Feedback, result['attempt_id']):
            return
        reading = {'resource_ref': check.source['resource_ref'], 'practice': {
            'check_id': check.check_id, 'attempt_id': result['attempt_id']}}
        index = check.source.get('question_index')
        if index is not None:
            reading['locator'] = {'kind': 'quiz', 'question_index': index}
        request = AnswerRequest(request_id=uuid5(NAMESPACE_URL, 'teaching-feedback:' + result['attempt_id']),
            question='请根据我刚提交的这次答案和本题评价讲解，说明答案是否符合题意及原因，给一个下一步建议。我未提供解题过程时，请勿推测我的思考过程。',
            reading_context=reading)
        db.add(Feedback(attempt_id=result['attempt_id'], check_id=check.check_id, owner=check.owner,
            revision=activity.revision, status='pending', request=request.model_dump(mode='json'), created_at=time.time()))

    def enqueue_pending(self):
        """Crash-safe delivery: a stable request ID recovers a turn accepted before a crash."""
        if not self.available or not self.learning.turns:
            return
        with Session(self.engine) as db:
            pending = [(r.attempt_id, r.owner) for r in db.scalars(select(Feedback)
                .where(Feedback.status == 'pending').order_by(Feedback.created_at).limit(8))]
        for aid, owner in pending:
            try:
                with Session(self.engine) as db:
                    event = db.get(Feedback, aid)
                    check = db.get(LearningCheck, event.check_id)
                    course, topic, request = check.course_id, check.topic_id, event.request
                    self.checks.owned(db, owner, event.check_id, allow_saved=True)
                from .rollout import phase
                if phase(self.learning, owner, course) < 4:
                    continue
                turn = self.learning.turns.accept(owner, course, topic, AnswerRequest.model_validate(request))
            except HTTPException as exc:
                if exc.status_code == 503:
                    continue
                if exc.status_code == 409:
                    from .db_models import LearningAnswerRun
                    with Session(self.engine) as db:
                        active = db.scalar(select(LearningAnswerRun.turn_id).where(
                            LearningAnswerRun.owner == owner, LearningAnswerRun.course_id == course,
                            LearningAnswerRun.topic_id == topic, LearningAnswerRun.status.in_(['accepted', 'running'])).limit(1))
                    if active:
                        continue  # A real active turn defers feedback; a source conflict does not.
                with self.checks._write('learning-checks:' + owner) as db:
                    event = db.get(Feedback, aid)
                    if event.status == 'pending':
                        event.status, event.error = 'failed', 'CONTEXT_UNAVAILABLE'
                continue
            with self.checks._write('learning-checks:' + owner) as db:
                event = db.get(Feedback, aid)
                if event.status == 'pending':
                    event.status, event.turn_id = 'queued', turn['turn_id']
