"""Existing durable queue/ledger integration for versioned artifact operations."""
from copy import deepcopy
import hashlib
import json
import threading

from app.services.job_store import create_job, get_job, update_job, JobKind, JobStatus
from app.chat.tasks.task_store import get_task_store
from app.services.durable_task_handlers import DurableTaskExecutionError


def reply_for(outcome, conversation_id):
    artifact = outcome.get('artifact')
    return {
        'message': {'role': 'assistant', 'content': outcome['message']},
        'conversation': {'conversation_id': conversation_id},
        'action': {'name': 'artifact.read' if outcome['status'] == 'answered' else 'artifact.revise'},
        'artifacts': [{**artifact, **outcome.get('artifact_reference', {})}] if artifact else [],
        'sources': [], 'trace': {'path': 'fast'}, 'artifact_revision': outcome,
    }


class ArtifactRevisionCommandService:
    _lock = threading.RLock()

    def __init__(self, task_store=None):
        self.tasks = task_store or get_task_store()

    def submit(self, *, state, source, current_question, prior_pending=None):
        command = {'state': deepcopy(state), 'current_question': current_question, 'prior_pending': deepcopy(prior_pending),
                   'deadline_seconds': 600, 'execution_timeout_seconds': 300}
        identity = json.dumps([state['owner_user_id'], state['conversation_id'], state['operation_id'], state['question'], state['reference']], ensure_ascii=False)
        task_id = 'revision-' + hashlib.sha256(identity.encode()).hexdigest()[:28]
        with self._lock:
            job = get_job(task_id)
            if job is None:
                job = create_job(kind=JobKind.REVISE_ARTIFACT, edu_job_id=task_id,
                    owner_user_id=state['owner_user_id'], course_id=source['course_id'],
                    scope_type=source.get('scope_type', 'course'), scope_id=source.get('scope_id'),
                    input_summary={'title': source.get('title') or '资料修改',
                        'material_id': source['material_id'], 'material_type': source['material_type'],
                        'base_version': source['version'], 'conversation_id': state['conversation_id']})
            try:
                self.tasks.enqueue(task_id=task_id, workflow_type='artifact_revision', handler_version=1,
                    owner_user_id=state['owner_user_id'], course_id=source['course_id'],
                    scope_type=source.get('scope_type', 'course'), scope_id=source.get('scope_id'),
                    command=command, config_snapshot_id=None, idempotency_key=task_id, max_attempts=3)
            except Exception:
                update_job(task_id, status=JobStatus.FAILED, message='资料修改任务入队失败', error_code='TASK_ENQUEUE_FAILED', error_message='请重试，原资料未改变')
                return {'status': 'failed', 'message': '资料修改任务入队失败，原资料未改变'}
        return {'status': 'queued', 'message': '资料处理任务已提交，可在后台任务中查看进度；成功修改后保留原版并保存新版本。',
                'task_id': job.edu_job_id, 'artifact_reference': state['reference']}


class ArtifactRevisionTaskHandler:
    def __init__(self, manager=None, conversations=None, llm=None, authorize=None):
        self.manager, self.conversations, self.llm, self.authorize = manager, conversations, llm, authorize

    def __call__(self, command, context):
        from core.course_storage import CourseStorageManager
        from core.conversation_storage import conversation_storage
        from app.artifact_revision.service import ArtifactRevisionService
        from app.chat.application.knowledge_context import authorize_workspace
        from app.chat.domain.contracts import ChatRequestV2
        from app.chat.agents.report_generation import get_fallback_llm
        state = deepcopy(command['state'])
        if state['owner_user_id'] != context.owner_user_id:
            raise DurableTaskExecutionError('REVISION_FORBIDDEN', '任务不属于当前账号')
        manager = self.manager or CourseStorageManager()
        conversations = self.conversations or conversation_storage
        request = ChatRequestV2(owner=state['owner_user_id'], question=state['question'],
            conversation_id=state['conversation_id'], course_id=state['reference']['source_course_id'], actor_role=state.get('actor_role', 'teacher'))
        (self.authorize or authorize_workspace)(request)
        context.progress(10, 'read_original', '读取原版本并核对修改目标')
        service = ArtifactRevisionService(manager, self.llm or get_fallback_llm(),
            is_cancel_requested=context.is_cancel_requested,
            before_save=lambda: update_job(context.task_id, cancelable=False, step='saving_version', message='正在保存新版本和原版副本'))
        context.progress(30, 'revise_content', '正在理解意见并处理原文')
        outcome = service.run(owner_user_id=state['owner_user_id'], conversation_id=state['conversation_id'],
            course_id=state['course_id'], question=state['question'], operation_id=state['operation_id'],
            artifact_reference=state['reference'], scope_id=state.get('scope_id'), frozen_target=True,
            current_question=command['current_question'])
        outcome['operation_id'] = state['operation_id']
        outcome['task_id'] = context.task_id
        if outcome['status'] in {'failed', 'conflict', 'not_applicable'}:
            raise DurableTaskExecutionError('REVISION_CONFLICT' if outcome['status'] == 'conflict' else 'REVISION_FAILED', outcome['message'])
        if outcome['status'] == 'answered' and command.get('prior_pending'):
            outcome['pending'] = command['prior_pending']
            outcome['awaiting_clarification'] = True
        if outcome['status'] == 'completed':
            # Both snapshots must be readable before a task can advertise success.
            ref = outcome['artifact_reference']
            kind = ref['artifact_type']
            base = int(outcome['base_version_id'].removeprefix('v'))
            service.read_version(owner_user_id=context.owner_user_id, course_id=ref['source_course_id'],
                artifact_type=kind, artifact_id=ref['artifact_id'], version=base)
            context.progress(95, 'verify_versions', f'已保存第 {base + 1} 版，保留第 {base} 版副本')
            outcome['message'] = f'已保存《{ref.get("title", "资料")}》第 {base + 1} 版，原第 {base} 版副本已保留。可在后台任务中打开结果。'
            result_ref = {'resource_type': 'artifact_revision', 'course_id': ref['source_course_id'],
                'material_type': 'report' if kind == 'report_outline' else kind, 'material_id': ref['artifact_id'],
                'version': base + 1, 'base_version': base, 'actor_role': state.get('actor_role', 'teacher'), 'operation_id': state['operation_id']}
        else:
            # The processing turn completed; no modified material is advertised.
            result_ref = {'resource_type': 'artifact_conversation', 'course_id': request.course_id,
                'conversation_id': request.conversation_id, 'actor_role': state.get('actor_role', 'teacher'), 'outcome_status': outcome['status']}
        existing = conversations.get_state(request.conversation_id).get('pending_operation') or {}
        if outcome.get('pending') and (not existing or existing.get('id') == state['operation_id']):
            conversations.update_state(request.conversation_id, {'pending_operation': {
                'id': state['operation_id'], 'kind': 'artifact_revision', 'owner': state['owner_user_id'],
                'course_id': state['course_id'], 'scope_id': state.get('scope_id'), 'revision_pending': outcome['pending']}})
        else:
            existing = conversations.get_state(request.conversation_id).get('pending_operation') or {}
            if existing.get('id') == state['operation_id']:
                conversations.update_state(request.conversation_id, {'pending_operation': None})
        result = reply_for(outcome, request.conversation_id)
        # Keep a durable, useful history entry even if the browser was closed.
        if outcome['status'] == 'completed':
            ref = outcome['artifact_reference']
            from urllib.parse import urlencode
            target = ('#student-resources?' if state.get('actor_role') == 'student' else '#resources?') + urlencode({'course_id': ref['source_course_id'], 'material_type': result_ref['material_type'], 'material_id': ref['artifact_id']})
            result['message']['content'] += f'\n[打开资料]({target})'
        conversations.append_message(request.conversation_id, 'assistant', result['message']['content'])
        conversations.update_state(request.conversation_id, {'latest_revision_outcome': {k: v for k, v in outcome.items() if k not in {'artifact', 'pending'}}, 'artifact_reference': outcome.get('artifact_reference') or state['reference']})
        return {**result, 'saved': True, 'result_ref': result_ref, 'completion_message': outcome['message']}
