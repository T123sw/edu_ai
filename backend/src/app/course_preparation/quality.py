"""Source, route, native content and whole-course gates with targeted repairs."""
from pydantic import Field,model_validator
from .schemas import Contract,Identifier,ShortText
from .manifest import CourseManifest
from .research_contracts import ResearchState
from .research_agent import ResearchAgent,ResearchError
from .tool_registry import digest
from .runner import StepResult

RULE_VERSION='preparation-delivery-v1'


class DeliveryIssue(Contract):
    artifact_ids: tuple[Identifier,...]=Field(min_length=1,max_length=40)
    reason: ShortText


class CourseReview(Contract):
    decision: str
    checked_node_ids: tuple[Identifier,...]=Field(min_length=1,max_length=12)
    issues: tuple[DeliveryIssue,...]=Field(default=(),max_length=12)
    limitations: tuple[ShortText,...]=Field(default=(),max_length=12)
    @model_validator(mode='after')
    def valid(self):
        if self.decision not in ('pass','fail') or (self.decision=='pass')!= (not self.issues): raise ValueError('INVALID_COURSE_REVIEW')
        return self


def check_digest(checkpoint):
    return digest({'rules':RULE_VERSION,'brief':checkpoint['brief'],'plan':checkpoint['plan'],
        'evidence':checkpoint['node_evidence'],'memory_refs':checkpoint.get('memory_refs',{}),
        'artifacts':[(r['artifact_id'],r['spec_digest'],r['content_digest'],r['status']) for r in checkpoint['artifacts']]})


def candidate_manifest(context,checkpoint,request):
    course_id=request.target.course_id if request.target else 'learn-'+context.preparation_id.removeprefix('prep_')
    version=request.target.base_manifest_version+1 if request.target else 1
    nodes=[]
    for i,node in enumerate(checkpoint['plan']['nodes']):
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
        goal=request.goal,audience=checkpoint['brief']['audience'],estimated_minutes=sum(n['estimated_minutes'] for n in nodes),
        assumptions=checkpoint['brief'].get('assumptions',[]),nodes=nodes,quality_report_id='quality_'+check_digest(checkpoint),
        limitations=checkpoint.get('quality',{}).get('limitations',[]),created_by_preparation_id=context.preparation_id)


class QualityStages:
    def __init__(self,repository,generation,memory,model_factory):
        self.repository,self.generation,self.memory,self.model_factory=repository,generation,memory,model_factory

    def review(self,context):
        checkpoint=dict(context.checkpoint); self.memory.validate(context,checkpoint)
        state=ResearchState.model_validate(checkpoint['research_state'])
        ResearchAgent._validate_path(state.path,state)
        request=self.repository.get(owner_user_id=context.owner_user_id,preparation_id=context.preparation_id).request
        artifacts=[self.generation.read_result(context.owner_user_id,checkpoint['generation_receipts'][digest(spec)]) for spec in checkpoint['resource_specs']]
        checkpoint['artifacts']=artifacts
        failed=[r for r in artifacts if r['status']!='draft']
        if failed:
            checkpoint['quality']={'decision':'fail','issues':[{'artifact_ids':[r['artifact_id']], 'reason':r.get('error_code') or 'RESOURCE_NOT_READY'} for r in failed]}
            return StepResult(checkpoint,'repair')
        candidate_manifest(context,checkpoint,request)
        model=self.model_factory(context,request,checkpoint).model
        tool={'type':'function','function':{'name':'review_course_delivery','description':'审阅实际完整课程资源和路径，逐节点检查；阻塞问题指出需修订的 artifact_ids。',
            'parameters':CourseReview.model_json_schema()}}
        decision,args=model.decide({'phase':'course_review','request':request.model_dump(mode='json'),
            'brief':checkpoint['brief'],'path':checkpoint['plan'],'node_evidence':checkpoint['node_evidence'],
            'artifacts':[{'artifact_id':r['artifact_id'],'node_id':r['spec']['node_id'],'kind':r['resource_type'],'content':r['content']['content']} for r in artifacts]},[tool],timeout=90)
        self.memory.validate(context,checkpoint)
        if decision!='review_course_delivery': raise ResearchError('COURSE_REVIEW_INVALID','审阅工具不合法')
        review=CourseReview.model_validate(args)
        if set(review.checked_node_ids)!={n['node_key'] for n in checkpoint['plan']['nodes']}:
            raise ResearchError('COURSE_REVIEW_INCOMPLETE','审阅未覆盖全部节点')
        allowed={r['artifact_id'] for r in artifacts}
        if any(not set(issue.artifact_ids)<=allowed for issue in review.issues): raise ValueError('UNKNOWN_REPAIR_TARGET')
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
        by_spec={r['spec_digest']:r for r in checkpoint['artifacts']}
        specifications=[]
        for spec in checkpoint['resource_specs']:
            artifact=by_spec[digest(spec)]
            specifications.append({**spec,'revision':spec['revision']+1,'revision_feedback':affected[artifact['artifact_id']]} if artifact['artifact_id'] in affected else spec)
        checkpoint.update(resource_specs=specifications,production_repairs=repairs,
            invalidated_drafts=[*checkpoint.get('invalidated_drafts',[]),{'artifacts':[r for r in checkpoint['artifacts'] if r['artifact_id'] in affected]}])
        checkpoint.pop('quality',None); checkpoint.pop('candidate_manifest',None)
        return StepResult(checkpoint,'produce')
