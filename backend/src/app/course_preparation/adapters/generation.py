"""Durable resource jobs write private drafts and return exact readback receipts."""
import json
from datetime import datetime
from types import SimpleNamespace
from .memory import PreparationMemory
from ..artifact_store import ArtifactStore
from ..generation_contracts import ResourceSpec
from ..tool_registry import digest
from ..generation_gateway import PreparationHarnessGateway


class GenerationAdapter:
    def __init__(self,repository,task_store):
        self.repository,self.task_store=repository,task_store
        self.artifacts=ArtifactStore(repository)

    def submit(self,context,spec,action_id):
        artifact=self.artifacts.create(context,action_id,spec)
        job_id='generate_'+artifact['artifact_id']
        existing=self.task_store.get_durable(job_id)
        if existing is None:
            self.task_store.enqueue(task_id=job_id,workflow_type='preparation_resource',handler_version=1,
                owner_user_id=context.owner_user_id,course_id=None,scope_type='preparation',scope_id=context.preparation_id,
                command={'artifact_id':artifact['artifact_id']},config_snapshot_id=None,idempotency_key=job_id,
                max_attempts=2,deadline_at=datetime.fromisoformat(context.deadline))
        elif existing.owner_user_id!=context.owner_user_id or existing.command!={'artifact_id':artifact['artifact_id']}:
            raise PermissionError('CHILD_JOB_IDENTITY_CONFLICT')
        return {'artifact_id':artifact['artifact_id'],'job_id':job_id}

    def reconcile(self,context,spec,action_id):
        # create is a SQL readback-or-insert under the existing action key. A
        # failed task lookup propagates; it is not interpreted as missing.
        return self.submit(context,spec,action_id)

    def read_result(self,owner,receipt):
        artifact=self.artifacts.get(owner,receipt['artifact_id'],content=True)
        job=self.task_store.get_durable(receipt['job_id'])
        if job is None: raise LookupError('CHILD_JOB_MISSING')
        if job.owner_user_id!=owner: raise PermissionError('CHILD_OWNER_CHANGED')
        if artifact['status']!='draft':
            if job.status in ('failed','canceled') and artifact['status'] not in ('failed',):
                artifact={**artifact,'status':'failed','error_code':job.error_code or 'CHILD_FAILED'}
            return artifact
        if not artifact['content'] or digest(artifact['content'])!=artifact['content_digest']:
            raise ValueError('ARTIFACT_CONTENT_MISSING_OR_CHANGED')
        from app.chat.harness.reviewed_report import verified_review
        from app.chat.harness.reviewed_resource import verified_resource,validate_resource
        if artifact['resource_type']=='report': valid=verified_review(artifact['content'])
        else:
            validate_resource(artifact['resource_type'],artifact['content']['content'])
            checked={**artifact['content'],**artifact['content']['content']} if artifact['resource_type']=='classroom' else artifact['content']
            valid=verified_resource(checked,artifact['resource_type'])
        if not valid: raise ValueError('ARTIFACT_REVIEW_MISSING_OR_STALE')
        return artifact


def automatic_payload(spec,artifact):
    # A owns the normalized builder. Keep the historical v1 reader available
    # while that module is being integrated; never feed a v2 spec to it.
    try:
        from ..generation_context import automatic_payload as build_payload
    except ModuleNotFoundError as exc:
        if exc.name != 'app.course_preparation.generation_context':
            raise
        if spec.get('schema_version', 1) != 1:
            from ..research_agent import ResearchError
            raise ResearchError('PREPARATION_CONTEXT_UNAVAILABLE', '规范化教学上下文构造器尚未接入') from exc
        return _legacy_automatic_payload(spec,artifact)
    return build_payload(spec,artifact)


def _legacy_automatic_payload(spec,artifact):
    spec=ResourceSpec.model_validate(spec)
    # No confirmed_outline or fabricated user confirmation is sent.
    return SimpleNamespace(resource_type=spec.resource_type,title=spec.title,subject=spec.title,
        audience=spec.audience,focus=f'语言：{spec.language}；学习时间：{spec.minutes} 分钟；目标：'+ '；'.join(spec.objectives)+
            '。学习检查：'+spec.learning_check+'。需修复：'+'；'.join(spec.revision_feedback)+('。这是对现有资料的修订，请保留未要求修改的正确内容与结构。' if spec.original_content else ''),
        research_context='\n\n'.join(f"[{e['source_id']}] {e['claim']}\n原文：{e['quote']}\n来源：{e['url']}" for e in spec.evidence)+('\n现有资料全文（修改基线，不是额外事实来源）：\n'+json.dumps(spec.original_content,ensure_ascii=False) if spec.original_content else ''),
        research_sources=[{'url':e['url'],'source_id':e['source_id']} for e in spec.evidence],
        harness_chapters=[{'title':'概念与机制'},{'title':'案例与面试表达'},{'title':'学习检查'}],
        harness_execution_context={'stage':'write_and_review','authorization':'preparation_automatic_policy',
            'policy_version':spec.preparation_policy},
        preparation_policy=spec.preparation_policy,owner=artifact['owner_user_id'],course_id='',material_id=artifact['resource_id'])


class PreparationResourceHandler:
    def __init__(self,application_factory): self.application_factory=application_factory

    def __call__(self,command,context):
        app=self.application_factory(); store=ArtifactStore(app.repository)
        artifact=store.claim(context.owner_user_id,command['artifact_id'])
        if artifact is None:
            existing=store.get(context.owner_user_id,command['artifact_id'])
            if existing['status']=='draft': return {'saved':True,'result_ref':{'kind':'preparation_draft','artifact_id':existing['artifact_id']}}
            raise RuntimeError('RESOURCE_ALREADY_RUNNING')
        try:
            from ..research_dependencies import agent_factory
            username=PreparationMemory(app.repository).subject(context.owner_user_id)
            configured=agent_factory(username,artifact['spec']['config_snapshot']).model.gateway
            parent=app.repository.get_public(context.owner_user_id,artifact['preparation_id'])
            gateway=PreparationHarnessGateway(configured,store,artifact,deadline=parent['budget']['deadline'],canceled=context.is_cancel_requested)
            payload=automatic_payload(artifact['spec'],artifact)
            if artifact['resource_type']=='report':
                from app.chat.harness.reviewed_report import generate_reviewed_report
                body,state=generate_reviewed_report(payload,gateway=gateway)
                result={'artifact_type':'report','title':payload.title,'content':body,'generation_state':state}
            elif artifact['resource_type']=='classroom':
                from .classroom import generate_classroom_draft
                result=generate_classroom_draft(payload,gateway=gateway,context=context,artifact=artifact)
            else:
                from app.chat.harness.reviewed_resource import ReviewedResourceGenerator
                result=ReviewedResourceGenerator(gateway=gateway,progress=context.progress).generate(payload,
                    job_id=context.task_id,config_snapshot_id='')['artifacts'][0]
            if context.is_cancel_requested(): raise RuntimeError('CANCELED')
            saved=store.save(artifact,result)
            return {'saved':True,'result_ref':{'kind':'preparation_draft','artifact_id':saved['artifact_id']}}
        except Exception as exc:
            store.fail(artifact,getattr(exc,'code','RESOURCE_GENERATION_FAILED'))
            raise
