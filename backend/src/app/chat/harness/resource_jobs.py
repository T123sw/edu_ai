"""Resource job capabilities. Model selects the target; application checks ownership."""
from __future__ import annotations
import asyncio
import json


def submit_classroom(command, manager, *, existing_job=None):
    from app.services.classroom_service import submit_classroom_generation_job
    from .resource_profiles import resource_contract
    config = command.config
    organization = config.get('harness_organization') or {}
    options = config.get('classroom_options') or {}
    return asyncio.run(submit_classroom_generation_job(
        existing_job=existing_job, course_id=command.course_id, owner=command.owner_user_id, course_storage_manager=manager,
        scope_type=command.scope_type, scope_id=command.scope_id,
        requirement=config['title'] + '\n' + config['focus'] + '\n已确认需求：\n' + config['confirmed_outline'] + '\n原生制作交接约定：\n' + resource_contract('classroom'),
        topic=config['title'], audience=config['audience'], objectives=organization.get('objectives', []),
        web_research_context=json.dumps({'evidence': config['research_context'], 'organization': organization}, ensure_ascii=False),
        source_mode=command.source_mode, selected_doc_ids=command.selected_doc_ids,
        enable_web_search=False, enable_tts=options.get('enable_tts'),
        include_visuals=options.get('include_visuals'),
        duration_minutes=options.get('duration_minutes'),
        video_preferences=options.get('video_preferences'),
        idempotency_key=command.idempotency_key, material_id=command.material_id,
        material_metadata={'harness_config': config, 'review_policy': command.review_policy},
        deadline_seconds=command.deadline_seconds,
    ))


class ResourceJobsMixin:
    def find_resource_jobs(self, args):
        from .tools import RESOURCE_LABELS
        from app.services.job_store import JobKind
        if not self.request.owner or not self.request.course_id or not self.list_report_jobs:
            return {'lookup_status': 'unavailable', 'candidates': [], 'next_cursor': None}
        kinds = [JobKind('generate_' + kind) for kind in RESOURCE_LABELS]
        page = self.list_report_jobs(owner_user_id=self.request.owner, course_id=self.request.course_id,
                                    kinds=kinds, limit=20, cursor=args.cursor)
        candidates = []
        for job in page.items:
            kind = str(getattr(job.kind, 'value', job.kind)).removeprefix('generate_')
            if job.owner_user_id != self.request.owner or job.course_id != self.request.course_id or kind not in RESOURCE_LABELS:
                continue
            summary = job.input_summary or {}
            config = summary.get('config') or (summary.get('material_metadata') or {}).get('harness_config') or {}
            candidates.append({'task_id': job.edu_job_id, 'resource_type': kind, 'title': summary.get('title'),
                'status': str(getattr(job.status, 'value', job.status)), 'scope_id': job.scope_id,
                'retry_of_job_id': getattr(job, 'retry_of_job_id', None),
                'source_conversation_id': config.get('harness_conversation_id')})
        return {'lookup_status': 'candidates_found' if candidates else 'not_found_in_page',
                'candidates': candidates, 'next_cursor': page.next_cursor, 'selection': 'unresolved'}

    def _resource_job(self, task_id, *, cancel=False):
        from .tools import RESOURCE_LABELS
        job = self.get_job(task_id)
        kind = str(getattr(getattr(job, 'kind', None), 'value', getattr(job, 'kind', None))).removeprefix('generate_')
        if (not job or job.owner_user_id != self.request.owner or job.course_id != self.request.course_id
                or kind not in RESOURCE_LABELS or (job.result_ref or {}).get('course_id', job.course_id) != self.request.course_id):
            raise PermissionError('resource_job_not_found')
        if cancel and task_id not in self.session.data['jobs']:
            raise PermissionError('resource_job_not_in_this_conversation')
        return job, kind

    def query_resource_job(self, args):
        job, kind = self._resource_job(args.task_id)
        if kind == 'report':
            return self.query_report_job(args)
        status = str(getattr(job.status, 'value', job.status))
        result = {'task_id': args.task_id, 'resource_type': kind, 'status': status,
                  'progress': job.progress, 'title': (job.input_summary or {}).get('title'),
                  'result_ref': job.result_ref, 'verification': None, 'failure_reason': getattr(job, 'error_message', None)}
        if status == 'succeeded':
            reference = dict(job.result_ref)
            if kind == 'classroom':
                reference.update(material_type='classroom', material_id=reference.get('material_id') or reference.get('classroom_id'))
            artifact = self.read_artifact(reference, self.request.owner)
            from .reviewed_resource import verified_resource
            passed = verified_resource(artifact, kind)
            result['verification'] = {'decision': 'pass' if passed else 'fail', 'checks': 'version_bound_resource_review'}
            if kind in ('classroom', 'quiz') and ((artifact or {}).get('generation_state') or {}).get('resource_review', {}).get('decision') == 'skipped':
                result['verification'].update(checks='version_bound_structural_validation', semantic_review='skipped')
            if passed:
                result['artifact'] = {'artifact_id': job.result_ref.get('material_id') or job.result_ref.get('classroom_id'),
                    'artifact_type': kind, 'title': artifact.get('title'),
                    'content': artifact.get('content') or {'stage': artifact.get('stage'), 'scenes': artifact.get('scenes')}}
        return result

    def cancel_resource_job(self, args):
        _, kind = self._resource_job(args.task_id, cancel=True)
        job = self.cancel_job(args.task_id, owner_user_id=self.request.owner)
        return {'task_id': args.task_id, 'resource_type': kind, 'status': str(getattr(job.status, 'value', job.status))}
