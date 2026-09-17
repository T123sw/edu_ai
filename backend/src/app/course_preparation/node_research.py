"""Second research pass checks one node's teaching evidence, not a fixed search quota."""
from pydantic import Field, model_validator
from .schemas import Contract, Identifier, ShortText
from .research_agent import ResearchError


class NodeEvidenceDecision(Contract):
    node_key: Identifier
    sufficient: bool
    reason: ShortText
    source_ids: tuple[Identifier,...]=Field(default=(),max_length=12)
    gap_queries: tuple[ShortText,...]=Field(default=(),max_length=3)

    @model_validator(mode='after')
    def coherent(self):
        if self.sufficient and (self.gap_queries or not self.source_ids): raise ValueError('充分依据必须有来源且无缺口')
        if not self.sufficient and not self.gap_queries: raise ValueError('必须说明待补充的具体查询')
        return self


def review_node(model,state,node,*,timeout=60,preferences=None):
    context={'phase':'research_nodes','request':{'goal':state.brief.topic},'brief':state.brief.model_dump(mode='json'),
        'node':node.model_dump(mode='json'),'summary':state.summary.model_dump(mode='json'),
        'evidence':[e.model_dump(mode='json') for e in state.evidence if e.source_id in node.source_ids],
        'preferences':preferences or {}}
    tool={'type':'function','function':{'name':'assess_node_evidence',
        'description':'核对本节点的目标、活动与自测是否有足够已读材料；仅对具体缺口提出补充查询。',
        'parameters':NodeEvidenceDecision.model_json_schema()}}
    name,args=model.decide(context,[tool],timeout=timeout)
    if name!='assess_node_evidence': raise ResearchError('INVALID_NODE_REVIEW','节点研究返回了未挂载工具')
    result=NodeEvidenceDecision.model_validate(args)
    if result.node_key!=node.node_key or not set(result.source_ids)<=set(node.source_ids):
        raise ResearchError('INVALID_NODE_EVIDENCE','节点或来源不属于本次检查范围')
    return result
