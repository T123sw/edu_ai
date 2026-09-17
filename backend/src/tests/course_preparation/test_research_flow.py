from uuid import uuid4

import pytest

from app.course_preparation.research_contracts import ResearchRequest, ResearchState
from app.course_preparation.research_agent import ResearchAgent, ResearchError


def request():
    return ResearchRequest(request_id=uuid4(), goal='用30分钟理解递归终止条件',
                           overrides={'total_minutes': 30})


def brief():
    return {'topic': '递归', 'audience': '初学者', 'language': 'zh-CN', 'total_minutes': 30,
            'assumptions': ['已了解函数'], 'requirements': [
                {'requirement_id': 'req1', 'text': '理解递归终止条件', 'source_quote': '理解递归终止条件'}]}


def summary(source_id):
    return {'overview': '递归必须有终止条件。', 'findings': [
        {'finding_id': 'f1', 'claim': '递归需要终止条件',
         'citations': [{'source_id': source_id, 'quote': '递归需要终止条件，否则调用不会结束。'}]}],
        'unresolved_gaps': [], 'limitations': []}


def path(source_id):
    return {'title': '递归入门', 'summary': '通过正反例理解递归终止。', 'nodes': [
        {'node_key': 'n1', 'title': '终止条件', 'objectives': ['能够找出终止条件'],
         'prerequisite_keys': [], 'minutes': 30, 'requirement_ids': ['req1'],
         'finding_ids': ['f1'], 'source_ids': [source_id],
         'learning_activities': ['阅读示例并修改终止条件'], 'self_check': '去掉终止条件会怎样？'}],
        'limitations': []}


class Sources:
    def __init__(self):
        self.searches = []
        self.reads = []

    def search(self, query, *, limit, timeout):
        self.searches.append(query)
        return [{'url': 'https://example.edu/recursion', 'title': '递归说明', 'snippet': '摘要不能作为正文'}]

    def read(self, url, *, timeout):
        self.reads.append(url)
        return '递归需要终止条件，否则调用不会结束。\n' + '通过递减参数逐步达到终止状态。' * 20


class Model:
    def __init__(self):
        self.mounts = []

    def decide(self, context, tools, *, timeout):
        self.mounts.append([t['function']['name'] for t in tools])
        if context['phase'] == 'intent':
            return 'save_preparation_brief', brief()
        if context['phase'] == 'research':
            if not context['candidates']:
                return 'search_sources', {'query': '递归 终止条件 教程'}
            if not context['evidence']:
                return 'fetch_source', {'candidate_id': context['candidates'][0]['candidate_id']}
            return 'save_research_summary', summary(context['evidence'][0]['source_id'])
        if context['phase'] == 'plan':
            return 'save_course_plan', path(context['evidence'][0]['source_id'])
        return 'submit_path_review', {'decision': 'pass', 'issues': [], 'checked_requirement_ids': ['req1']}


def run(agent, state=None):
    state = state or ResearchState()
    for _ in range(12):
        state = agent.step(request(), state)
        if state.phase == 'done':
            return state
    raise AssertionError('did not finish')


def test_intent_search_read_summary_path_and_independent_review():
    sources, model = Sources(), Model()
    result = run(ResearchAgent(model=model, sources=sources))
    assert sources.searches and sources.reads
    assert result.path.nodes[0].source_ids == (result.evidence[0].source_id,)
    assert result.review.decision == 'pass'
    assert model.mounts[0] == ['save_preparation_brief']
    assert model.mounts[-1] == ['submit_path_review']
    assert result.calls == 6


def test_resume_reuses_real_evidence_instead_of_researching_again():
    sources = Sources()
    agent = ResearchAgent(model=Model(), sources=sources)
    state = ResearchState()
    for _ in range(3):
        state = agent.step(request(), state)
    restored = ResearchState.model_validate_json(state.model_dump_json())
    result = run(agent, restored)
    assert result.phase == 'done'
    assert len(sources.searches) == len(sources.reads) == 1


def test_summary_cannot_cite_search_snippet_or_invented_evidence():
    class Invented(Model):
        def decide(self, context, tools, **kwargs):
            if context['phase'] == 'research':
                return 'save_research_summary', summary('made-up')
            return super().decide(context, tools, **kwargs)
    agent = ResearchAgent(model=Invented(), sources=Sources())
    state = agent.step(request(), ResearchState())
    state = agent.step(request(), state)
    assert state.phase == 'research' and state.summary is None
    assert state.last_error['code'] == 'INVALID_TOOL_RESULT'


@pytest.mark.parametrize('mutation', [
    lambda p: p['nodes'][0].update(prerequisite_keys=['n1']),
    lambda p: p['nodes'][0].update(minutes=300),
    lambda p: p['nodes'][0].update(requirement_ids=['unknown']),
    lambda p: p['nodes'][0].update(source_ids=['invented']),
    lambda p: p['nodes'][0].update(finding_ids=['invented']),
])
def test_invalid_path_cannot_finish(mutation):
    class Invalid(Model):
        def decide(self, context, tools, **kwargs):
            name, args = super().decide(context, tools, **kwargs)
            if name == 'save_course_plan':
                mutation(args)
            return name, args
    agent = ResearchAgent(model=Invalid(), sources=Sources())
    state = ResearchState()
    for _ in range(5):
        state = agent.step(request(), state)
    assert state.phase == 'plan' and state.path is None


def test_unmounted_tool_never_executes():
    class Wrong(Model):
        def decide(self, *args, **kwargs):
            return 'fetch_source', {'candidate_id': 'bad'}
    sources = Sources()
    state = ResearchAgent(model=Wrong(), sources=sources).step(request(), ResearchState())
    assert state.last_error['code'] == 'TOOL_NOT_AVAILABLE'
    assert not sources.reads


def test_rejected_review_repairs_path_then_stops_at_limit():
    class Reject(Model):
        def decide(self, context, tools, **kwargs):
            if context['phase'] == 'review':
                return 'submit_path_review', {'decision': 'fail', 'issues': ['目标与活动不匹配'],
                                            'checked_requirement_ids': ['req1']}
            return super().decide(context, tools, **kwargs)
    with pytest.raises(ResearchError, match='QUALITY_GATE_FAILED'):
        run(ResearchAgent(model=Reject(), sources=Sources()))


def test_read_next_excerpt_does_not_reuse_first_excerpt():
    class LongSources(Sources):
        def read(self, url, **kwargs):
            self.reads.append(url)
            return '开头正文。' * 1000 + '后续正文。' * 1000
    sources = LongSources()
    agent = ResearchAgent(model=Model(), sources=sources)
    state = ResearchState()
    for _ in range(3):
        state = agent.step(request(), state)
    from app.course_preparation.research_contracts import FetchArgs
    second = agent._execute('fetch_source', FetchArgs(candidate_id=state.candidates[0].candidate_id, offset_chars=5000),
                            request(), state, timeout=10, reserve=None)
    assert len(second.evidence) == 2
    assert second.evidence[1].offset_chars == 5000
    assert second.evidence[1].content.startswith('后续正文')
    with pytest.raises(ValueError, match='已读取'):
        agent._execute('fetch_source', FetchArgs(candidate_id=state.candidates[0].candidate_id),
                       request(), state, timeout=10, reserve=None)


def test_reviewer_can_send_incorrect_intent_back_for_correction():
    from app.course_preparation.research_contracts import PathReview
    agent = ResearchAgent(model=Model(), sources=Sources())
    state = run(agent).model_copy(update={'phase': 'review'})
    failed = agent._execute('submit_path_review', PathReview(decision='fail',
        issues=['需求理解遗漏了用户原话'], checked_requirement_ids=['req1'], repair_phase='intent'),
        request(), state, timeout=10, reserve=None)
    assert failed.phase == 'intent' and failed.path is None and failed.summary is None
    assert agent.tools(failed.phase)[0]['function']['name'] == 'save_preparation_brief'


def test_budget_is_reserved_before_external_model_and_fetch():
    checkpoints = []
    class Observed(Model):
        def decide(self, context, tools, **kwargs):
            assert checkpoints[-1].calls == context['calls']
            return super().decide(context, tools, **kwargs)
    class ObservedSources(Sources):
        def read(self, url, **kwargs):
            assert checkpoints[-1].reads == 1
            return super().read(url, **kwargs)
    agent = ResearchAgent(model=Observed(), sources=ObservedSources())
    state = ResearchState()
    for _ in range(3):
        state = agent.step(request(), state, reserve=checkpoints.append)
    assert len(state.evidence) == 1


def test_validation_feedback_preserves_failed_submission_for_targeted_repair():
    class Invalid(Model):
        def decide(self, context, tools, **kwargs):
            name, args = super().decide(context, tools, **kwargs)
            if name == 'save_course_plan':
                args['nodes'][0]['minutes'] = 300
            return name, args
    agent = ResearchAgent(model=Invalid(), sources=Sources())
    state = ResearchState()
    for _ in range(5):
        state = agent.step(request(), state)
    assert state.last_error['attempted_tool'] == 'save_course_plan'
    assert state.last_error['arguments']['nodes'][0]['minutes'] == 300
    assert state.path is None


def test_exhausted_read_budget_unmounts_retrieval_and_allows_grounded_summary():
    agent = ResearchAgent(model=Model(), sources=Sources())
    state = ResearchState()
    for _ in range(3):
        state = agent.step(request(), state)
    state = state.model_copy(update={'reads': 8})
    assert [t['function']['name'] for t in agent.tools('research', state)] == ['save_research_summary']
    next_state = agent.step(request(), state)
    assert next_state.phase == 'plan' and next_state.summary
    assert next_state.reads == 8


def test_exhausted_search_budget_still_allows_reading_existing_candidates():
    agent = ResearchAgent(model=Model(), sources=Sources())
    state = ResearchState(phase='research', searches=6)
    assert [t['function']['name'] for t in agent.tools('research', state)] == ['fetch_source', 'save_research_summary']


@pytest.mark.parametrize('same_page,ambiguous', [(True, False), (False, False), (True, True)])
def test_quote_resolution_requires_unique_exact_match_on_same_read_page(same_page, ambiguous):
    from app.course_preparation.research_contracts import ResearchSummary
    agent = ResearchAgent(model=Model(), sources=Sources())
    state = ResearchState()
    for _ in range(3):
        state = agent.step(request(), state)
    first = state.evidence[0]
    second = first.model_copy(update={'source_id': 'later_excerpt', 'offset_chars': 5000,
        'url': first.url if same_page else 'https://another.example.edu/page',
        'content': '这里是另一段独特的真实原文内容。'})
    evidence = (first, second)
    if ambiguous:
        evidence += (second.model_copy(update={'source_id': 'duplicate_excerpt'}),)
    state = state.model_copy(update={'evidence': evidence})
    draft = summary(first.source_id)
    draft['findings'][0]['citations'][0]['quote'] = second.content
    if same_page and not ambiguous:
        result = agent._execute('save_research_summary', ResearchSummary.model_validate(draft),
                                request(), state, timeout=10, reserve=None)
        assert result.summary.findings[0].citations[0].source_id == second.source_id
        assert result.trace[-1]['event'] == 'citation_span_resolved'
    else:
        with pytest.raises(ValueError, match='不匹配'):
            agent._execute('save_research_summary', ResearchSummary.model_validate(draft),
                           request(), state, timeout=10, reserve=None)


def test_incremental_findings_keep_verified_sources_and_finalize_by_id():
    from app.course_preparation.research_contracts import Finding,FinalizeSummary
    agent=ResearchAgent(model=Model(),sources=Sources(),incremental_findings=True)
    state=ResearchState()
    for _ in range(3): state=agent.step(request(),state)
    found=Finding.model_validate(summary(state.evidence[0].source_id)['findings'][0])
    state=agent._execute('record_research_finding',found,request(),state,timeout=1,reserve=None)
    assert state.phase=='research' and state.summary is None
    assert state.draft_findings[0].citations[0].quote in state.evidence[0].content
    with pytest.raises(ValueError): agent._execute('record_research_finding',found,request(),state,timeout=1,reserve=None)
    final=agent._execute('finalize_research_summary',FinalizeSummary(overview='递归终止',finding_ids=['f1']),request(),state,timeout=1,reserve=None)
    assert final.phase=='plan' and final.summary.findings==(found,)
    assert 'save_research_summary' not in [t['function']['name'] for t in agent.tools('research',state)]


def test_evidence_handles_bind_actual_raw_text_and_reject_unknown_handles():
    from app.course_preparation.research_contracts import ReferencedFinding
    from app.course_preparation.evidence_spans import span_registry
    agent=ResearchAgent(model=Model(),sources=Sources())
    state=ResearchState()
    for _ in range(3): state=agent.step(request(),state)
    registry=span_registry(state); handle=next(iter(registry))
    decision=ReferencedFinding(finding_id='f1',claim='终止条件避免无限调用',citation_refs=[handle])
    result=agent._execute('record_evidence_finding',decision,request(),state,timeout=1,reserve=None)
    assert result.draft_findings[0].citations[0].quote in state.evidence[0].content
    bad=decision.model_copy(update={'citation_refs':('q999_1',)})
    with pytest.raises(ValueError): agent._execute('record_evidence_finding',bad,request(),state,timeout=1,reserve=None)


def test_end_of_source_is_explicit_and_read_tool_unmounted_when_exhausted():
    agent=ResearchAgent(model=Model(),sources=Sources())
    state=ResearchState()
    for _ in range(3): state=agent.step(request(),state)
    evidence=state.evidence[0]
    assert evidence.total_chars==len(evidence.content) and evidence.next_offset is None
    assert 'fetch_source' not in [t['function']['name'] for t in agent.tools('research',state)]
    assert 'save_research_summary' in [t['function']['name'] for t in agent.tools('research',state)]


def test_brief_quote_can_reference_explicit_route_changes():
    from app.course_preparation.schemas import PreparationRequest
    from app.course_preparation.research_contracts import ResearchBrief
    request=PreparationRequest(request_id=uuid4(),operation='adjust_course',goal='调整学习路径',
        target={'course_id':'course','base_manifest_version':1,'base_route_version':1},requested_changes=['理解递归终止条件'])
    agent=ResearchAgent.__new__(ResearchAgent)
    state=ResearchState()
    agent._execute('save_preparation_brief',ResearchBrief.model_validate(brief()),request,state,timeout=10,reserve=lambda _:None)
    invalid=ResearchBrief.model_validate({**brief(),'requirements':[{'requirement_id':'r','text':'虚构要求','source_quote':'从未要求的内容'}]})
    with pytest.raises(ValueError,match='要求原话'):
        agent._execute('save_preparation_brief',invalid,request,state,timeout=10,reserve=lambda _:None)
