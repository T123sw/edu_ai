"""Source, route, native content and whole-course gates with targeted repairs."""
from typing import Literal
from copy import deepcopy
from pydantic import Field,model_validator,ValidationError
from .schemas import Contract,Identifier,ShortText
from .manifest import CourseManifest
from .research_contracts import ResearchState
from .research_agent import ResearchAgent,ResearchError
from .tool_registry import digest
from .runner import StepResult

RULE_VERSION='preparation-delivery-v2'


class DeliveryIssue(Contract):
    artifact_ids: tuple[Identifier,...]=Field(min_length=1,max_length=40)
    reason: ShortText


class CourseReview(Contract):
    decision: Literal['pass', 'fail']
    checked_node_ids: tuple[Identifier,...]=Field(min_length=1,max_length=12)
    issues: tuple[DeliveryIssue,...]=Field(default=(),max_length=12)
    limitations: tuple[ShortText,...]=Field(default=(),max_length=12)
    @model_validator(mode='after')
    def valid(self):
        if self.decision not in ('pass','fail') or (self.decision=='pass')!= (not self.issues): raise ValueError('INVALID_COURSE_REVIEW')
        return self


def check_digest(checkpoint):
    return digest({'rules':RULE_VERSION,'brief':checkpoint['brief'],'plan':checkpoint['plan'],
        'route_only_adjustment':checkpoint.get('route_only_adjustment',False),
        'target_snapshot':checkpoint.get('target_snapshot'),'evidence':checkpoint['node_evidence'],'memory_refs':checkpoint.get('memory_refs',{}),
        'retained_artifacts':[(r['artifact_id'],r['content_digest']) for r in checkpoint.get('retained_artifacts',[])],
        'artifacts':[(r['artifact_id'],r['spec_digest'],r['content_digest'],r['status']) for r in checkpoint['artifacts']]})


def local_manifest(context, checkpoint, request):
    base = deepcopy(checkpoint['target_snapshot']['manifest'])
    node = next(n for n in base['nodes'] if n['node_id'] == request.target.node_id)
    old = checkpoint['target_snapshot']['resource']
    for artifact in checkpoint['artifacts']:
        resource = {'resource_id': artifact['resource_id'], 'resource_type': artifact['resource_type'],
            'version': artifact['resource_version'], 'content_sha256': artifact['content_digest'],
            'purpose': request.goal, 'required': old['required'] if old else False,
            'order': old['order'] if old else max((r['order'] for r in node['resources']), default=0)+1,
            'objective_ids': old['objective_ids'] if old else [o['objective_id'] for o in node['objectives']],
            'source_refs': list(dict.fromkeys(e['source_id'] for e in artifact['spec']['evidence']))}
        if old:
            node['resources'] = [resource if r['resource_id']==old['resource_id'] else r for r in node['resources']]
            for check in node['checks']:
                if check['resource_id']==old['resource_id']:
                    check.update(resource_id=resource['resource_id'],resource_version=resource['version'])
        else: node['resources'].append(resource)
    base.update(manifest_id='manifest_'+digest([context.owner_user_id,base['course_id']])[:32],
        version=request.target.base_manifest_version+1, space='personal',
        created_by_preparation_id=context.preparation_id, quality_report_id='quality_'+check_digest(checkpoint),
        limitations=list(dict.fromkeys([*base.get('limitations',[]),*checkpoint.get('quality',{}).get('limitations',[])])))
    return CourseManifest.model_validate(base)


def candidate_manifest(context,checkpoint,request):
    if request.operation in ('supplement_node','revise_resource'):
        return local_manifest(context,checkpoint,request)
    course_id=request.target.course_id if request.target else 'learn-'+context.preparation_id.removeprefix('prep_')
    version=request.target.base_manifest_version+1 if request.target else 1
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
                'required':artifact['spec']['required'],'order':j+1,'objective_ids':[o['objective_id'] for o in objectives],
                'source_refs':list(dict.fromkeys(e['source_id'] for e in artifact['spec']['evidence']))})
            if artifact['resource_type']=='report':
                checks.append({'check_id':node['node_key']+':check','objective_ids':[o['objective_id'] for o in objectives],
                    'mode':'self_check','resource_id':artifact['resource_id'],'resource_version':artifact['resource_version'],
                    'locator':{'section_id':'学习检查'}})
        nodes.append({'node_id':node['node_key'],'title':node['title'],'order':i+1,'required':True,'objectives':objectives,
            'prerequisite_node_ids':node['prerequisite_keys'],'estimated_minutes':node['minutes'],'resources':resources,'checks':checks})
    return CourseManifest(manifest_id='manifest_'+digest([context.owner_user_id,course_id])[:32],course_id=course_id,
        version=version,route_version=(request.target.base_route_version+1 if request.target and request.target.base_route_version else version),
        goal=checkpoint['target_snapshot']['manifest']['goal'] if request.operation=='adjust_course' else request.goal,audience=checkpoint['brief']['audience'],estimated_minutes=sum(n['estimated_minutes'] for n in nodes),
        assumptions=checkpoint['brief'].get('assumptions',[]),nodes=nodes,quality_report_id='quality_'+check_digest(checkpoint),
        limitations=checkpoint.get('quality',{}).get('limitations',[]),created_by_preparation_id=context.preparation_id)


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
            checkpoint['quality']={'decision':'fail','issues':[{'artifact_ids':[r['artifact_id']], 'reason':r.get('error_code') or 'RESOURCE_NOT_READY'} for r in failed]}
            return StepResult(checkpoint,'repair')
        candidate_manifest(context,checkpoint,request)
        model=self.model_factory(context,request,checkpoint).model
        reviews = dict(checkpoint.get('node_quality_reviews', {}))
        current_digest = check_digest(checkpoint)
        if checkpoint.get('node_quality_digest') != current_digest:
            reviews = {}
        unchecked = next((node for node in checkpoint['plan']['nodes'] if node['node_key'] not in reviews), None)
        selected_artifacts = [r for r in artifacts if unchecked is None or r['spec']['node_id'] == unchecked['node_key']]
        tool={'type':'function','function':{'name':'review_course_delivery','description':'审阅资料与学习目标；逐节点检查，阻塞问题指出需要修订的 artifact_ids。',
            'parameters':CourseReview.model_json_schema()}}
        if unchecked:
            review_context = {'review_scope': '完整节点资源；检查该节点全部目标、引用、练习与跨资料一致性',
                'node': unchecked, 'node_evidence': checkpoint['node_evidence'][unchecked['node_key']],
                'artifacts': [{'artifact_id': r['artifact_id'], 'node_id': r['spec']['node_id'], 'kind': r['resource_type'],
                              'content': r['content']['content']} for r in selected_artifacts]}
        else:
            # Every full body has a digest-bound node review. The final pass checks
            # ordering and cross-node coverage using these reviews, not truncated bodies.
            review_context = {'review_scope': '整课衔接、目标覆盖、先修顺序和重复内容；全部正文已分别审阅',
                'node_reviews': reviews,
                'artifacts': [{'artifact_id': r['artifact_id'], 'node_id': r['spec']['node_id'],
                              'kind': r['resource_type'], 'objectives': r['spec']['objectives'],
                              'content_digest': r['content_digest']} for r in artifacts]}
        decision,args=model.decide({'phase':'course_review','request':request.model_dump(mode='json'),
            'brief':checkpoint['brief'],'path':checkpoint['plan'],'route_only_adjustment':checkpoint.get('route_only_adjustment',False),
            'last_schema_error':checkpoint.get('review_schema_error'), **review_context},[tool],timeout=90)
        self.memory.validate(context,checkpoint)
        if decision!='review_course_delivery': raise ResearchError('COURSE_REVIEW_INVALID','审阅工具不合法')
        try:review=CourseReview.model_validate(args)
        except ValidationError as exc:
            scope=unchecked['node_key'] if unchecked else '__course__'
            attempts=dict(checkpoint.get('review_schema_repairs',{}))
            attempts[scope]=attempts.get(scope,0)+1
            if attempts[scope]>2:raise ResearchError('COURSE_REVIEW_INVALID','审阅响应两次修正后仍不符合契约') from exc
            checkpoint.update(review_schema_repairs=attempts,review_schema_error={'scope':scope,
                'errors':[{'path':list(e['loc']),'message':e['msg']} for e in exc.errors(include_input=False)],
                'rejected_arguments':args,'instruction':'只修改工具参数结构，直接提供 decision、checked_node_ids、issues、limitations，不要包装在 json 字符串字段中。未通过合法审阅前不会交付。'})
            return StepResult(checkpoint)
        checkpoint.pop('review_schema_error',None)
        expected_nodes = {unchecked['node_key']} if unchecked else {n['node_key'] for n in checkpoint['plan']['nodes']}
        if set(review.checked_node_ids)!=expected_nodes:
            raise ResearchError('COURSE_REVIEW_INCOMPLETE','审阅未覆盖全部节点')
        allowed={r['artifact_id'] for r in artifacts}
        if any(not set(issue.artifact_ids)<=allowed for issue in review.issues): raise ValueError('UNKNOWN_REPAIR_TARGET')
        if unchecked and review.decision == 'pass':
            reviews[unchecked['node_key']] = review.model_dump(mode='json')
            checkpoint.update(node_quality_reviews=reviews, node_quality_digest=current_digest)
            return StepResult(checkpoint)
        checkpoint['quality']={**review.model_dump(mode='json'),'input_digest':check_digest(checkpoint),'rule_version':RULE_VERSION}
        if review.decision=='pass':
            checkpoint['candidate_manifest']=candidate_manifest(context,checkpoint,request).model_dump(mode='json')
        return StepResult(checkpoint,'commit' if review.decision=='pass' else 'repair')

    def repair(self,context):
        checkpoint=dict(context.checkpoint); self.memory.validate(context,checkpoint)
        repairs=checkpoint.get('production_repairs',0)+1
        if repairs>2: raise ResearchError('QUALITY_GATE_FAILED','两轮局部修复后仍未通过课程门禁')
        affected={key:[] for issue in checkpoint['quality']['issues'] for key in issue['artifact_ids']}
        for issue in checkpoint['quality']['issues']:
            for key in issue['artifact_ids']: affected[key].append(issue['reason'])
        if any(key.startswith('retained:') for key in affected):
            raise ResearchError('RETAINED_CONTENT_REQUIRES_SEPARATE_REVISION','保留资料的内容检查未通过，需要明确修订该资料；不擅自重生成原资料')
        by_spec={r['spec_digest']:r for r in checkpoint['artifacts']}
        specifications=[]
        for spec in checkpoint['resource_specs']:
            artifact=by_spec[digest(spec)]
            specifications.append({**spec,'revision':spec['revision']+1,'revision_feedback':affected[artifact['artifact_id']]} if artifact['artifact_id'] in affected else spec)
        checkpoint.update(resource_specs=specifications,production_repairs=repairs,
            invalidated_drafts=[*checkpoint.get('invalidated_drafts',[]),{'artifacts':[r for r in checkpoint['artifacts'] if r['artifact_id'] in affected]}])
        checkpoint.pop('quality',None); checkpoint.pop('candidate_manifest',None)
        return StepResult(checkpoint,'produce')
