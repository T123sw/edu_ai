"""Budgeted research projection. Durable state retains every original byte.

Size is UTF-8 JSON bytes, NOT provider token usage. If protected requirements and
locators exceed the budget, fail explicitly; never silently truncate a demand.
"""
import json
from .research_contracts import ResearchState
from .evidence_spans import evidence_context, span_registry
from .research_agent import ResearchError


def _size(value):
    return len(json.dumps(value,ensure_ascii=False,separators=(',',':')).encode())


def read_research_evidence(state, *, source_id=None, citation_ref=None, offset_chars=0, limit=5000):
    state=state if isinstance(state,ResearchState) else ResearchState.model_validate(state)
    if bool(source_id)==bool(citation_ref):
        raise ValueError('指定且仅指定 source_id 或 citation_ref')
    if not 0 <= offset_chars or not 1 <= limit <= 5000: raise ValueError('INVALID_EVIDENCE_WINDOW')
    if citation_ref:
        citation=span_registry(state).get(citation_ref)
        if citation is None: raise ValueError('UNKNOWN_CITATION_REF')
        return {**citation,'citation_ref':citation_ref}
    evidence=next((e for e in state.evidence if e.source_id==source_id),None)
    if evidence is None: raise ValueError('UNKNOWN_SOURCE_ID')
    if offset_chars>=len(evidence.content): raise ValueError('EVIDENCE_OFFSET_OUT_OF_RANGE')
    return {**evidence.model_dump(mode='json',exclude={'content'}),
        'content':evidence.content[offset_chars:offset_chars+limit],
        'window_offset_chars':offset_chars,
        'window_next_offset':offset_chars+limit if offset_chars+limit<len(evidence.content) else None}


def build_research_context_view(state, *, required_ids, max_bytes):
    state=state if isinstance(state,ResearchState) else ResearchState.model_validate(state)
    required=set(required_ids)
    available={e.source_id for e in state.evidence}|{c.candidate_id for c in state.candidates}
    available|={r.requirement_id for r in state.brief.requirements} if state.brief else set()
    available|={f.finding_id for f in state.draft_findings}
    available|={f.finding_id for f in state.summary.findings} if state.summary else set()
    available|=set(span_registry(state))
    if not required<=available: raise ValueError('UNKNOWN_REQUIRED_ID')
    view=state.model_dump(mode='json',exclude={'trace','evidence','candidates','last_error'})
    view['last_error']=({k:v for k,v in state.last_error.items() if k not in ('arguments','rejected_model_response')}
                        if state.last_error else None)
    view['candidates']=[c.model_dump(mode='json',exclude={'snippet'}) for c in state.candidates]
    expanded=evidence_context(state)
    view['evidence']=[{**{k:v for k,v in e.items() if k!='passages'},'passages':[],
        'content_omitted':True,'read_tool':'read_research_evidence'} for e in expanded]
    view['context_view']={'schema_version':1,'max_bytes':max_bytes,'estimated_bytes':0,
        'actual_usage':None,'omitted':['trace','candidate_snippets','unselected_evidence_passages'],
        'read_tool':'read_research_evidence'}
    def fits():
        # Reserve space for byte count growth; final fixed-point count is exact.
        return _size(view)+16<=max_bytes
    if not fits(): raise ResearchError('RESEARCH_CONTEXT_BUDGET','原要求、缺口、结论和定位超出预算，需要独立研究会话')
    for i,evidence in enumerate(expanded):
        for passage in evidence['passages']:
            if passage['citation_ref'] in required:
                view['evidence'][i]['passages'].append(passage)
    if not fits(): raise ResearchError('RESEARCH_CONTEXT_BUDGET','必需的精确引文超出预算')
    order=sorted(range(len(expanded)),key=lambda i:expanded[i]['source_id'] not in required)
    for i in order:
        for passage in expanded[i]['passages']:
            if passage['citation_ref'] in required: continue
            view['evidence'][i]['passages'].append(passage)
            if not fits(): view['evidence'][i]['passages'].pop()
        view['evidence'][i]['content_omitted']=len(view['evidence'][i]['passages'])!=len(expanded[i]['passages'])
    for _ in range(4): view['context_view']['estimated_bytes']=_size(view)
    if _size(view)>max_bytes: raise ResearchError('RESEARCH_CONTEXT_BUDGET','研究视图预算不足')
    return view
