"""Second research pass checks one node's teaching evidence, not a fixed search quota."""
from pydantic import Field, model_validator
from .schemas import Contract, Identifier, ShortText
from .research_agent import ResearchError


class NodeEvidenceDecision(Contract):
    node_key: Identifier
    sufficient: bool
    reason: ShortText
    source_ids: tuple[Identifier,...]=Field(default=())
    gap_queries: tuple[ShortText,...]=Field(default=())

    @model_validator(mode='after')
    def coherent(self):
        if self.sufficient and (self.gap_queries or not self.source_ids): raise ValueError('充分依据必须有来源且无缺口')
        if not self.sufficient and not self.gap_queries: raise ValueError('必须说明待补充的具体查询')
        return self


class NodeEvidenceAssessment(Contract):
    sufficient: bool
    reason: ShortText
    source_refs: tuple[Identifier,...]=Field(default=())
    gap_queries: tuple[ShortText,...]=Field(default=())


def review_node(model,state,node,*,timeout=60,preferences=None):
    evidence=[e for e in state.evidence if e.source_id in node.source_ids]
    refs={f'source_{i+1}':e.source_id for i,e in enumerate(evidence)}
    inverse={value:key for key,value in refs.items()}
    context={'phase':'research_nodes','request':{'goal':state.brief.topic},'brief':state.brief.model_dump(mode='json'),
        'node':node.model_dump(mode='json',exclude={'source_ids','finding_ids'}),
        'findings':[{'claim':f.claim,'source_refs':[inverse[c.source_id] for c in f.citations if c.source_id in inverse]}
            for f in state.summary.findings if f.finding_id in node.finding_ids],
        'evidence':[{**e.model_dump(mode='json',exclude={'source_id'}),'source_ref':key}
            for key,e in zip(refs,evidence)],'preferences':preferences or {}}
    schema=NodeEvidenceAssessment.model_json_schema()
    schema['properties']['source_refs']['items']['enum']=list(refs)
    tool={'type':'function','function':{'name':'assess_node_evidence',
        'description':'核对本节点是否有足够已读材料；source_refs 只选本次发放的短编号。', 'parameters':schema}}
    name,args=model.decide(context,[tool],timeout=timeout)
    if name!='assess_node_evidence': raise ResearchError('INVALID_NODE_REVIEW','节点研究返回了未挂载工具')
    result=NodeEvidenceAssessment.model_validate(args)
    if not set(result.source_refs)<=refs.keys(): raise ResearchError('INVALID_NODE_EVIDENCE','来源不属于本次检查范围')
    return NodeEvidenceDecision(node_key=node.node_key,sufficient=result.sufficient,reason=result.reason,
        source_ids=tuple(refs[key] for key in result.source_refs),gap_queries=result.gap_queries)
