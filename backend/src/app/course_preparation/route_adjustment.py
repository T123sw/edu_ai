"""Adjust presentation of an existing route without inventing a new research task."""
import re
from pydantic import Field
from .schemas import Contract,Identifier,ShortText
from .runner import StepResult
from .research_agent import ResearchError


def eligible(request):
    command='\n'.join([request.goal,*request.requested_changes])
    return (request.operation=='adjust_course' and not request.uploads
        and any(x in command for x in ('保留原资料','保留现有资料','保留所有资料','不重新生成资料'))
        and bool(re.search(r'(只|仅)[^。；;]*(时间|时长|顺序|排序|标题)',command))
        and not any(x in command for x in ('新增节点','删除节点','增加节点','新增知识点','删除知识点','更改目标')))


class RouteNode(Contract):
    node_id: Identifier
    title: ShortText
    minutes: int=Field(strict=True,ge=1)
    prerequisite_node_ids: tuple[Identifier,...]=Field(default=())


class RouteEdit(Contract):
    nodes: tuple[RouteNode,...]=Field(min_length=1)


def validate(request,checkpoint):
    if not eligible(request):raise ResearchError('TARGET_SCOPE_CHANGED','请求不属于保留资料的路径调整')
    base=checkpoint['target_snapshot']['manifest']
    old={n['node_id']:n for n in base['nodes']};nodes=checkpoint['plan']['nodes']
    if len(nodes)!=len(old) or {n['node_key'] for n in nodes}!=set(old):raise ResearchError('TARGET_SCOPE_CHANGED','保留资料的路径调整不能增删节点')
    command='\n'.join([request.goal,*request.requested_changes])
    if re.search(r'保留[^。；;]*(?:节点顺序|原顺序)',command) and [n['node_key'] for n in nodes]!=list(old):
        raise ResearchError('TARGET_SCOPE_CHANGED','本次明确保留节点顺序')
    for n in nodes:
        original=old[n['node_key']]
        if not set(request.overrides.required_resource_types)<={r['resource_type'] for r in original['resources']}:
            raise ResearchError('REQUIRED_RESOURCE_UNAVAILABLE','保留资料的路径调整不能同时要求尚不存在的新资料类型')
        if n['objectives']!=[o['text'] for o in original['objectives']]:raise ResearchError('TARGET_SCOPE_CHANGED','路径调整不能修改原目标')
        if not any(x in command for x in ('标题','重命名')) and n['title']!=original['title']:raise ResearchError('TARGET_SCOPE_CHANGED','本次没有要求修改节点标题')


def plan(stages,context):
    checkpoint=dict(context.checkpoint);request=stages._request(context);stages.memory.validate(context,checkpoint)
    base=checkpoint['target_snapshot']['manifest']
    tool={'type':'function','function':{'name':'save_route_adjustment','description':'只返回原节点的顺序、标题、时间和先修，不增加节点或改写资料。','parameters':RouteEdit.model_json_schema()}}
    name,args=stages.agent_factory(context,request,checkpoint).model.decide({'phase':'route_adjustment','request':request.model_dump(mode='json'),'base_manifest':base},[tool],timeout=90)
    if name!='save_route_adjustment':raise ResearchError('INVALID_ROUTE_TOOL','路径工具不合法')
    edit=RouteEdit.model_validate(args);old={n['node_id']:n for n in base['nodes']}
    if any(n.node_id not in old for n in edit.nodes):raise ResearchError('TARGET_SCOPE_CHANGED','不能新增节点')
    checkpoint['plan']={'title':base['goal'],'summary':'按当前要求调整现有路径，保留全部资料及原文依据。','nodes':[
        {'node_key':n.node_id,'title':n.title,'minutes':n.minutes,'prerequisite_keys':list(n.prerequisite_node_ids),
         'objectives':[o['text'] for o in old[n.node_id]['objectives']],'self_check':'继续使用原节点准确版本的理解检查'} for n in edit.nodes],'limitations':base.get('limitations',[])}
    checkpoint['brief']={'goal':request.goal,'audience':base['audience'],'language':request.overrides.language or 'zh-CN',
        'total_minutes':sum(n.minutes for n in edit.nodes),'assumptions':base.get('assumptions',[])}
    checkpoint['node_evidence']={n.node_id:[] for n in edit.nodes}
    checkpoint['research_summary']={'overview':'使用已交付课程的原资料与来源；本次没有新知识或新资料制作要求。','findings':[]}
    validate(request,checkpoint)
    return StepResult(checkpoint,'research_nodes')
