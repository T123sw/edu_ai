"""Source, route, native content and whole-course gates with targeted repairs."""
from typing import Literal
from copy import deepcopy
import json
from pydantic import Field,model_validator,ValidationError
from .schemas import Contract,Identifier,ShortText
from .manifest import CourseManifest
from .research_contracts import ResearchState
from .research_agent import ResearchAgent,ResearchError
from .tool_registry import digest
from .runner import StepResult

RULE_VERSION='preparation-delivery-v15-structural-quiz'
REVIEW_RESPONSE_CORRECTIONS = 2
REVIEW_TRANSIENT_ERRORS = {'PROVIDER_TIMEOUT', 'PROVIDER_UNAVAILABLE', 'HARNESS_UNAVAILABLE', 'HARNESS_SHUTDOWN_FAILED'}

from .resource_alignment import (validate_artifact, resource_objectives, resource_checks,
    validate_manifest_locations, objective_coverage_basis, preparation_metadata, duration_summary, node_requirement_issues, node_objective_issues)
from .generation_failures import recovery_scope


class DeliveryIssue(Contract):
    artifact_ids: tuple[Identifier,...]=Field(min_length=1)
    reason: ShortText


class CourseReview(Contract):
    decision: Literal['pass', 'fail']
    checked_node_ids: tuple[Identifier,...]=Field(min_length=1)
    issues: tuple[DeliveryIssue,...]=Field(default=())
    limitations: tuple[ShortText,...]=Field(default=())
    @model_validator(mode='after')
    def valid(self):
        if self.decision not in ('pass','fail') or (self.decision=='pass')!= (not self.issues): raise ValueError('INVALID_COURSE_REVIEW')
        return self


def review_response_retry(checkpoint, *, scope, input_digest, code, errors, arguments, references, nodes):
    """Correct only the rejected review, retaining resources and accepted node reviews."""
    attempts = dict(checkpoint.get('review_schema_repairs', {}))
    if checkpoint.get('review_schema_repair_digest') not in (None, input_digest):
        attempts = {}
    attempts[scope] = attempts.get(scope, 0) + 1
    if attempts[scope] > REVIEW_RESPONSE_CORRECTIONS:
        raise ResearchError(code, '审阅响应两次纠正后仍不合法；已保留资源与检查点')
    rejected = json.dumps(arguments, ensure_ascii=False, default=str)
    checkpoint.update(review_schema_repairs=attempts, review_schema_repair_digest=input_digest,
        review_schema_error={'scope': scope, 'code': code, 'errors': errors,
            'rejected_arguments': arguments if len(rejected) <= 6000 else rejected[:6000],
            'allowed_artifact_ids': list(references), 'expected_checked_node_ids': sorted(nodes),
            'instruction': '重新提交 review_course_delivery 的合法参数：decision、checked_node_ids、issues、limitations。'
                'artifact_ids 只能从当前资源短编号列表中原样选择；checked_node_ids 必须完整覆盖本轮节点。'
                '保留有依据的内容问题，只纠正响应结构与引用，不编造编号、不改写资料、不直接宣布通过。'})
    return StepResult(checkpoint)


def review_provider_retry(checkpoint, *, scope, input_digest, error):
    previous = checkpoint.get('review_provider_retry', {})
    same_input = previous.get('scope') == scope and previous.get('input_digest') == input_digest
    attempt = previous.get('attempt', 0) + 1 if same_input else 1
    if attempt > 2:
        raise error
    checkpoint['review_provider_retry'] = {'scope': scope, 'input_digest': input_digest,
        'attempt': attempt, 'code': error.code}
    # Release the worker between retries. Global call/token/deadline budgets still apply.
    return StepResult(checkpoint, wait_seconds=5 * attempt)


def check_digest(checkpoint):
    # Hash actual inputs, not just digest fields that could conceal a mutated body.
    def identity(row):
        return {key:row.get(key) for key in ('artifact_id','resource_id','resource_version',
            'resource_type','spec','spec_digest','content','content_digest','status')}
    return digest({'rules':RULE_VERSION,'brief':checkpoint['brief'],'plan':checkpoint['plan'],
        'resource_specs':checkpoint.get('resource_specs'),
        'route_only_adjustment':checkpoint.get('route_only_adjustment',False),
        'target_snapshot':checkpoint.get('target_snapshot'),'evidence':checkpoint['node_evidence'],
        'memory_refs':checkpoint.get('memory_refs',{}), 'memory_view':checkpoint.get('memory_view'),
        'retained_artifacts':[identity(r) for r in checkpoint.get('retained_artifacts',[])],
        'artifacts':[identity(r) for r in checkpoint['artifacts']]})


def local_manifest(context, checkpoint, request):
    base = deepcopy(checkpoint['target_snapshot']['manifest'])
    node = next(n for n in base['nodes'] if n['node_id'] == request.target.node_id)
    old = checkpoint['target_snapshot']['resource']
    for artifact in checkpoint['artifacts']:
        resource = {'resource_id': artifact['resource_id'], 'resource_type': artifact['resource_type'],
            'version': artifact['resource_version'], 'content_sha256': artifact['content_digest'],
            'purpose': request.goal, 'required': old['required'] if old else False,
            'order': old['order'] if old else max((r['order'] for r in node['resources']), default=0)+1,
            'objective_ids': resource_objectives(artifact), 'objective_coverage': objective_coverage_basis(artifact),
            'source_refs': list(dict.fromkeys(e['source_id'] for e in artifact['spec']['evidence']))}
        if old:
            node['resources'] = [resource if r['resource_id']==old['resource_id'] else r for r in node['resources']]
            node['checks']=[c for c in node['checks'] if c['resource_id']!=old['resource_id']]
            node['checks'].extend(resource_checks(artifact,node['node_id']))
        else: node['resources'].append(resource)
    base.update(manifest_id='manifest_'+digest([context.owner_user_id,base['course_id']])[:32],
        version=request.target.base_manifest_version+1, space='personal',
        created_by_preparation_id=context.preparation_id, quality_report_id='quality_'+check_digest(checkpoint),
        limitations=list(dict.fromkeys([*base.get('limitations',[]),*checkpoint.get('quality',{}).get('limitations',[])])))
    manifest=CourseManifest.model_validate(base)
    validate_manifest_locations(manifest,checkpoint['artifacts'])
    return manifest


def candidate_manifest(context,checkpoint,request,*,partial=False):
    if request.operation in ('supplement_node','revise_resource'):
        return local_manifest(context,checkpoint,request)
    if not partial and node_requirement_issues([*checkpoint['artifacts'], *checkpoint.get('retained_artifacts', [])], checkpoint['plan']['nodes']):
        raise ValueError('NODE_REQUIREMENT_COVERAGE_MISSING')
    if not partial and node_objective_issues([*checkpoint['artifacts'], *checkpoint.get('retained_artifacts', [])], checkpoint['plan']['nodes']):
        raise ValueError('NODE_OBJECTIVE_COVERAGE_MISSING')
    course_id=request.target.course_id if request.target else 'learn-'+context.preparation_id.removeprefix('prep_')
    version=request.target.base_manifest_version+1 if request.target else checkpoint.get('partial_delivery',{}).get('manifest_version',0)+1
    nodes=[]
    for i,node in enumerate(checkpoint['plan']['nodes']):
        if node['node_key'] in checkpoint.get('retained_node_ids',[]):
            retained=deepcopy(next(n for n in checkpoint['target_snapshot']['manifest']['nodes'] if n['node_id']==node['node_key']))
            retained.update(title=node['title'],order=i+1,estimated_minutes=node['minutes'],prerequisite_node_ids=node['prerequisite_keys'])
            nodes.append(retained)
            continue
        objectives=[{'objective_id':node['node_key']+':o'+str(j+1),'text':text} for j,text in enumerate(node['objectives'])]
        artifacts=[r for r in checkpoint['artifacts'] if r['spec']['node_id']==node['node_key'] and r['status']=='draft']
        resources=[]; checks=[]
        for j,artifact in enumerate(artifacts):
            resources.append({'resource_id':artifact['resource_id'],'resource_type':artifact['resource_type'],
                'version':artifact['resource_version'],'content_sha256':artifact['content_digest'],'purpose':artifact['spec']['title'],
                'required':artifact['spec']['required'],'order':j+1,'objective_ids':resource_objectives(artifact),
                'objective_coverage':objective_coverage_basis(artifact),
                'source_refs':list(dict.fromkeys(e['source_id'] for e in artifact['spec']['evidence']))})
            checks.extend(resource_checks(artifact,node['node_key']))
        node_specs = [s for s in checkpoint.get('resource_specs', []) if s['node_id'] == node['node_key']]
        pending_types = sorted({s['resource_type'] for s in node_specs} - {r['resource_type'] for r in artifacts}) if partial else []
        statuses = [checkpoint.get('resource_generation_states', {}).get(digest(s), 'pending')
                    for s in node_specs if s['resource_type'] in pending_types]
        state = 'ready' if not pending_types else 'failed' if 'failed' in statuses else 'generating' if 'running' in statuses else 'queued'
        nodes.append({'node_id':node['node_key'],'title':node['title'],'order':i+1,'required':True,'objectives':objectives,
            'delivery_state': ('partial' if resources else 'pending') if pending_types else 'ready',
            'generation_status': state,
            'pending_resource_types': pending_types,
            'prerequisite_node_ids':node['prerequisite_keys'],'estimated_minutes':node['minutes'],'resources':resources,'checks':checks})
    manifest=CourseManifest(manifest_id='manifest_'+digest([context.owner_user_id,course_id])[:32],course_id=course_id,
        version=version,route_version=(request.target.base_route_version+1 if request.target and request.target.base_route_version else 1),
        delivery_state='partial' if partial else 'complete',
        goal=checkpoint['target_snapshot']['manifest']['goal'] if request.operation=='adjust_course' else request.goal,audience=checkpoint['brief']['audience'],estimated_minutes=sum(n['estimated_minutes'] for n in nodes),
        assumptions=checkpoint['brief'].get('assumptions',[]),nodes=nodes,quality_report_id='quality_'+check_digest(checkpoint),
        limitations=checkpoint.get('quality',{}).get('limitations',[]),created_by_preparation_id=context.preparation_id)
    validate_manifest_locations(manifest,checkpoint['artifacts'])
    return manifest


def node_review_artifacts(artifacts):
    """Share identical teaching contexts while preserving every native body and binding."""
    from app.chat.harness.reviewed_resource import _review_model_view
    contexts, rows = {}, []
    for artifact in artifacts:
        teaching = artifact['spec'].get('teaching_context')
        reference = digest(teaching)
        contexts[reference] = teaching
        rows.append({'artifact_id': artifact['artifact_id'], 'node_id': artifact['spec']['node_id'],
            'kind': artifact['resource_type'], 'content': _review_model_view(artifact['content']['content']),
            'teaching_context_ref': reference, 'preparation': preparation_metadata(artifact),
            # Full audit histories stay persisted; review exact bodies and bindings here.
            'resource_review_receipt': {k: v for k, v in
                artifact['content'].get('generation_state', {}).get('resource_review', {}).items()
                if k in ('decision', 'method', 'content_sha256', 'preparation_sha256')},
            'spec_digest': artifact['spec_digest'], 'content_digest': artifact['content_digest']})
    return {'teaching_contexts': contexts, 'artifacts': rows}


class QualityStages:
    def __init__(self,repository,generation,memory,model_factory):
        self.repository,self.generation,self.memory,self.model_factory=repository,generation,memory,model_factory

    def review(self,context):
        checkpoint=dict(context.checkpoint); self.memory.validate(context,checkpoint)
        request=self.repository.get(owner_user_id=context.owner_user_id,preparation_id=context.preparation_id).request
        if checkpoint.get('route_only_adjustment'):
            from .route_adjustment import validate
            validate(request,checkpoint)
        else:
            state=ResearchState.model_validate(checkpoint['research_state'])
            ResearchAgent._validate_path(state.path,state)
        artifacts=[self.generation.read_result(context.owner_user_id,checkpoint['generation_receipts'][digest(spec)]) for spec in checkpoint['resource_specs']]
        checkpoint['artifacts']=artifacts
        from .retained_resources import read_retained
        checkpoint['retained_artifacts']=read_retained(self.repository,context,checkpoint)
        artifacts=[*artifacts,*checkpoint['retained_artifacts']]
        failed=[r for r in artifacts if r['status']!='draft']
        if failed:
            from app.chat.harness.classroom_policy import can_resume_classroom_without_review
            recoverable = [r for r in failed if can_resume_classroom_without_review(r)]
            if recoverable:
                receipts = dict(checkpoint['generation_receipts'])
                for artifact in recoverable:
                    receipts[artifact['spec_digest']] = self.generation.resume_classroom_delivery(
                        context, artifact['artifact_id'])
                checkpoint['generation_receipts'] = receipts
                return StepResult(checkpoint, 'produce')
            for artifact in failed:
                if not artifact.get('failure_detail'):
                    raise ResearchError(artifact.get('error_code') or 'FAILURE_DETAIL_MISSING','子任务缺少可安全恢复的错误分类')
                recovery_scope(artifact['failure_detail'])
            from .duration_reallocation import reallocate_duration_caps
            released = reallocate_duration_caps(artifacts, checkpoint['plan']['nodes'],
                request.overrides.total_minutes, checkpoint.get('duration_cap_origins', {}))
            checkpoint['quality']={'decision':'fail','issues':[{'artifact_ids':[r['artifact_id']],
                'reason':r.get('error_code') or 'RESOURCE_NOT_READY',
                **({'resource_duration_cap_minutes': released[r['artifact_id']], 'duration_cap_reallocated': True}
                   if r['artifact_id'] in released else {})} for r in failed]}
            return StepResult(checkpoint,'repair')
        alignment_issues=[]
        for artifact in artifacts:
            try: validate_artifact(artifact)
            except ValueError as exc:
                alignment_issues.append({'artifact_ids':[artifact['artifact_id']], 'reason':str(exc)})
        if not alignment_issues:
            if request.operation in ('create_course','adjust_course'):
                alignment_issues.extend(node_requirement_issues(artifacts,checkpoint['plan']['nodes']))
                alignment_issues.extend(node_objective_issues(artifacts,checkpoint['plan']['nodes']))
        if alignment_issues:
            checkpoint['quality']={'decision':'fail','issues':alignment_issues}
            return StepResult(checkpoint,'repair')
        try:
            candidate_manifest(context,checkpoint,request)
            checkpoint['duration_summary']=duration_summary(artifacts,checkpoint['plan']['nodes'],
                hard_limit=request.overrides.total_minutes)
        except ValueError as exc:
            raise ResearchError('COURSE_CONTRACT_INVALID',str(exc)) from exc
        reviews = dict(checkpoint.get('node_quality_reviews', {}))
        current_digest = check_digest(checkpoint)
        if checkpoint.get('node_quality_digest') != current_digest:
            reviews = {}
        unchecked = next((node for node in checkpoint['plan']['nodes'] if node['node_key'] not in reviews), None)
        # Quizzes and classrooms have passed deterministic resource checks above.
        # Never send their bodies/bindings to a second model under node/course
        # review, and never let that model target these resources for repair.
        selected_artifacts = [r for r in artifacts if r['resource_type'] not in ('classroom', 'quiz')
            and (unchecked is None or r['spec']['node_id'] == unchecked['node_key'])]
        expected_nodes = {unchecked['node_key']} if unchecked else {n['node_key'] for n in checkpoint['plan']['nodes']}
        references = {f'resource_{i+1}': r['artifact_id'] for i, r in enumerate(selected_artifacts)}
        aliases = {value: key for key, value in references.items()}
        schema = CourseReview.model_json_schema()
        schema['$defs']['DeliveryIssue']['properties']['artifact_ids']['items'] = {'type': 'string', 'enum': list(references)}
        schema['properties']['checked_node_ids']['items'] = {'type': 'string', 'enum': sorted(expected_nodes)}
        tool={'type':'function','function':{'name':'review_course_delivery','description':'审阅资料与学习目标；逐节点检查，阻塞问题指出需要修订的 artifact_ids。',
            'parameters':schema}}
        if unchecked:
            review_context = {'review_mode': 'node', 'review_scope': '本轮提供的报告等资源；检查目标、引用与跨资料一致性，排除习题和课堂内容审阅',
                'node': unchecked, 'node_evidence': checkpoint['node_evidence'][unchecked['node_key']],
                **node_review_artifacts(selected_artifacts),
                'duration_summary':checkpoint['duration_summary']}
        else:
            # Every in-scope body has a digest-bound node review. The final pass checks
            # ordering and cross-node coverage using these reviews, not truncated bodies.
            review_context = {'review_mode': 'course', 'review_scope': '整课衔接、目标覆盖、先修顺序和重复内容；报告等审阅范围内的正文已分别审阅',
                'node_reviews': reviews,
                'artifacts': [{'artifact_id': r['artifact_id'], 'node_id': r['spec']['node_id'],
                              'kind': r['resource_type'], 'objectives': r['spec']['objectives'],
                              'content_digest': r['content_digest']} for r in selected_artifacts],
                'duration_summary':checkpoint['duration_summary']}
        # Short references are local to these exact inputs; never guess a misspelled ID.
        review_context['artifacts'] = [{**row, 'artifact_id': aliases[row['artifact_id']]}
                                       for row in review_context['artifacts']]
        review_context['allowed_artifact_ids'] = list(references)
        review_context['expected_checked_node_ids'] = sorted(expected_nodes)
        review_context['resource_inventory'] = [
            {'node_id': r['spec']['node_id'], 'resource_type': r['resource_type'],
             'available': True, 'content_review': 'skipped' if r['resource_type'] in ('quiz', 'classroom') else 'in_scope'}
            for r in artifacts if r['spec']['node_id'] in expected_nodes]
        review_context['classroom_review_policy'] = (
            'AI 课堂按用户要求不做生成后审查，已单独执行结构校验。'
            '本轮只审阅传入的非课堂资源及课程路线；不评判课堂正文、讲解、配图、交互或其目标映射，'
            '不因课堂正文未提供而判缺失，不为课堂专属要求修订其他资源。')
        review_context['quiz_review_policy'] = (
            '习题生成后只校验可展示的结构，已完成的习题不参加逐题、节点或整课内容审查。'
            '习题正文及语义映射不在本轮输入内，不得因此判习题缺失或要求报告代替习题补做检查。')
        tool['function']['description'] = (
            '审阅当前节点提供的报告等资源正文、准确定位和教学目标；习题与课堂不在审阅范围。只提交该节点的审阅。' if unchecked else
            '基于已通过且摘要绑定的 node_reviews 核验整课先修顺序、跨节点衔接和目标覆盖；'
            '本轮不重复正文审阅，不以未重复附带正文或 teaching_contexts 为缺陷。')
        scope = unchecked['node_key'] if unchecked else '__course__'
        try:
            if selected_artifacts:
                model=self.model_factory(context,request,checkpoint).model
                decision,args=model.decide({'phase':'course_review','request':request.model_dump(mode='json'),
                    'brief':checkpoint['brief'],'path':checkpoint['plan'],'route_only_adjustment':checkpoint.get('route_only_adjustment',False),
                    'last_schema_error':checkpoint.get('review_schema_error'), **review_context},[tool],timeout=90)
            else:
                # Nodes/courses containing only quizzes and classrooms need no model review.
                decision,args='review_course_delivery',{'decision':'pass',
                    'checked_node_ids':sorted(expected_nodes),'issues':[],'limitations':[]}
        except ResearchError as exc:
            if exc.code not in REVIEW_TRANSIENT_ERRORS:
                raise
            self.memory.validate(context,checkpoint)
            return review_provider_retry(checkpoint, scope=scope, input_digest=current_digest, error=exc)
        self.memory.validate(context,checkpoint)
        def retry_response(code, errors):
            return review_response_retry(checkpoint, scope=scope,
                input_digest=current_digest, code=code, errors=errors, arguments=args,
                references=references, nodes=expected_nodes)
        if decision!='review_course_delivery':
            return retry_response('COURSE_REVIEW_INVALID', [{'message': '审阅工具必须为 review_course_delivery'}])
        try:review=CourseReview.model_validate(args)
        except ValidationError as exc:
            return retry_response('COURSE_REVIEW_INVALID',
                [{'path':list(e['loc']),'message':e['msg']} for e in exc.errors(include_input=False)])
        if set(review.checked_node_ids)!=expected_nodes:
            return retry_response('COURSE_REVIEW_INCOMPLETE', [{'message': '审阅节点与本轮范围不一致'}])
        allowed={r['artifact_id'] for r in selected_artifacts}
        resolved = tuple(issue.model_copy(update={'artifact_ids': tuple(references.get(key, key) for key in issue.artifact_ids)})
                         for issue in review.issues)
        if any(not set(issue.artifact_ids)<=allowed for issue in resolved):
            return retry_response('COURSE_REVIEW_UNKNOWN_RESOURCE', [{'message': 'artifact_ids 包含不属于本轮审阅的资源'}])
        review = review.model_copy(update={'issues': resolved})
        method = 'model_review_non_classroom_non_quiz' if selected_artifacts else 'structural_validation'
        checkpoint.pop('review_schema_error',None)
        if unchecked and review.decision == 'pass':
            reviews[unchecked['node_key']] = {**review.model_dump(mode='json'), 'method': method,
                'classroom_content_review': 'skipped', 'quiz_content_review': 'skipped'}
            checkpoint.update(node_quality_reviews=reviews, node_quality_digest=current_digest)
            return StepResult(checkpoint)
        limitations=list(dict.fromkeys([*review.limitations,
            *(item for review in reviews.values() for item in review.get('limitations',[])),
            *(item for r in artifacts for item in r['spec'].get('teaching_context',{}).get('limitations',[])),
            *(item for r in artifacts for item in r['content'].get('generation_state',{}).get('limitations',[])),
            *(['部分资源学习用时未知，尚未验证总用时。'] if checkpoint['duration_summary']['unknown_artifact_ids'] else [])]))
        checkpoint['quality']={**review.model_dump(mode='json'),'limitations':limitations,
            'input_digest':check_digest(checkpoint),'rule_version':RULE_VERSION,
            'method':method,'classroom_content_review':'skipped','quiz_content_review':'skipped'}
        if review.decision=='pass':
            checkpoint['candidate_manifest']=candidate_manifest(context,checkpoint,request).model_dump(mode='json')
        return StepResult(checkpoint,'commit' if review.decision=='pass' else 'repair')

    def repair(self,context):
        checkpoint=dict(context.checkpoint); self.memory.validate(context,checkpoint)
        repairs=checkpoint.get('production_repairs',0)+1
        affected={key:[] for issue in checkpoint['quality']['issues'] for key in issue['artifact_ids']}
        for issue in checkpoint['quality']['issues']:
            for key in issue['artifact_ids']: affected[key].append(issue['reason'])
        if any(key.startswith('retained:') for key in affected):
            raise ResearchError('RETAINED_CONTENT_REQUIRES_SEPARATE_REVISION','保留资料的内容检查未通过，需要明确修订该资料；不擅自重生成原资料')
        by_spec={r['spec_digest']:r for r in checkpoint['artifacts']}
        scopes={r['artifact_id']:recovery_scope(r['failure_detail']) if r.get('failure_detail') else 'content'
                for r in checkpoint['artifacts'] if r['artifact_id'] in affected}
        # Old checkpoints used one counter; conservatively retain their spent
        # content allowance. New work distinguishes re-review from rewriting.
        counts=dict(checkpoint.get('repair_counts',
                    {'content':checkpoint['production_repairs']} if checkpoint.get('production_repairs') else {}))
        for scope in set(scopes.values()):
            counts[scope]=counts.get(scope,0)+1
            if counts[scope]>2:
                raise ResearchError('QUALITY_GATE_FAILED',f'{scope} 两轮恢复后仍未通过课程门禁')
        specifications=[]
        cap_origins=dict(checkpoint.get('duration_cap_origins', {}))
        receipts=dict(checkpoint.get('generation_receipts',{}))
        for spec in checkpoint['resource_specs']:
            artifact=by_spec[digest(spec)]
            if artifact['artifact_id'] not in affected:
                specifications.append(spec)
                continue
            detail=artifact.get('failure_detail')
            scope=scopes[artifact['artifact_id']]
            if scope in ('review','provider'):
                resume=getattr(self.generation,'resume_review',None)
                if resume is None:
                    raise ResearchError('RESOURCE_RECOVERY_UNAVAILABLE','生成适配器尚未接入候选恢复，禁止重写正文')
                receipts[digest(spec)]=resume(context,artifact['artifact_id'],
                    recovery_key=digest([context.preparation_id,digest(spec),repairs]))
                specifications.append(spec)
            else:
                reasons=list(affected[artifact['artifact_id']])
                if detail and detail.get('message') and detail['message'] not in reasons:
                    reasons.append(detail['message'])
                revised_context = deepcopy(spec.get('teaching_context'))
                caps = [issue['resource_duration_cap_minutes'] for issue in checkpoint['quality']['issues']
                        if artifact['artifact_id'] in issue['artifact_ids'] and 'resource_duration_cap_minutes' in issue]
                if caps and revised_context is not None:
                    previous_cap = revised_context.get('resource_target_minutes')
                    original_cap = cap_origins.get(digest(spec), previous_cap)
                    reallocated = digest(spec) in cap_origins and any(
                        issue.get('duration_cap_reallocated') and artifact['artifact_id'] in issue['artifact_ids']
                        for issue in checkpoint['quality']['issues'])
                    revised_context['resource_target_minutes'] = original_cap
                    revised_context['resource_repair_target_minutes'] = min([*caps, *([original_cap] if original_cap else [])])
                    if reallocated:
                        reasons.append(f'其余已完成资料已释放时间，本资源本轮修订目标为 {revised_context["resource_repair_target_minutes"]:g} 分钟；'
                            '旧错误中的临时 maximum 已被此上限替代，节点和整课硬上限不变。正文仍须重新独立审阅和估算。')
                revised={**spec,'revision':spec['revision']+1,
                    **({'teaching_context': revised_context} if revised_context is not None else {}),
                    'revision_feedback':reasons,
                    'original_content':(artifact.get('content') or {}).get('content')
                        or (artifact.get('content') or {}).get('_review_candidate',{}).get('content')
                        or spec.get('original_content')}
                if caps and revised_context is not None:
                    cap_origins[digest(revised)] = original_cap
                elif digest(spec) in cap_origins:
                    cap_origins[digest(revised)] = cap_origins[digest(spec)]
                specifications.append(revised)
        checkpoint.update(resource_specs=specifications,generation_receipts=receipts,production_repairs=repairs,repair_counts=counts,
            duration_cap_origins=cap_origins,
            invalidated_drafts=[*checkpoint.get('invalidated_drafts',[]),{'artifacts':[r for r in checkpoint['artifacts'] if r['artifact_id'] in affected]}])
        checkpoint.pop('quality',None); checkpoint.pop('candidate_manifest',None)
        return StepResult(checkpoint,'produce')
