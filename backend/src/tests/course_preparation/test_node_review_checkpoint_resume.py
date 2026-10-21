from copy import deepcopy
from types import SimpleNamespace

from app.course_preparation.manual_retry import prepare_retry_checkpoint
from app.course_preparation.node_research import NodeEvidenceDecision
from app.course_preparation.research_agent import ResearchAgent
from app.course_preparation.research_stages import ResearchStages
from tests.course_preparation.test_research_flow import Model, Sources, run


def test_retry_retains_sources_and_completed_nodes_and_resumes_only_failed_review():
    state = run(ResearchAgent(model=Model(), sources=Sources()))
    first = state.path.nodes[0]
    second = first.model_copy(update={'node_key': 'n2'})
    state = state.model_copy(update={'path': state.path.model_copy(update={'nodes': (first, second)})})
    accepted = NodeEvidenceDecision(node_key=first.node_key, sufficient=True,
                                    reason='首节点已有独立审阅', source_ids=first.source_ids).model_dump(mode='json')
    old = {'research_state': state.model_dump(mode='json'), 'plan': state.path.model_dump(mode='json'),
           'source_snapshots': {'original': {'content': 'original source'}},
           'node_research_checks': {first.node_key: accepted}}
    unchanged = deepcopy(old)
    checkpoint, stage, _ = prepare_retry_checkpoint(None, None, SimpleNamespace(stage='research_nodes'), old)
    assert stage == 'research_nodes'
    assert checkpoint['source_snapshots'] == old['source_snapshots']
    assert checkpoint['plan'] == old['plan']
    reviewed = []

    def review(context, checkpoint, state, node):
        reviewed.append(node.node_key)
        return NodeEvidenceDecision(node_key=node.node_key, sufficient=True,
                                    reason='第二节点重新审阅通过', source_ids=node.source_ids)

    repository = SimpleNamespace(checkpoint=lambda *args: None)
    stages = ResearchStages(repository, lambda *args: None, None, node_reviewer=review)
    result = stages.research_nodes(SimpleNamespace(checkpoint=checkpoint, deadline=None))
    assert reviewed == ['n2']
    assert result.next_stage == 'produce'
    assert result.checkpoint['node_research_checks'][first.node_key] == accepted
    assert set(result.checkpoint['node_evidence']) == {first.node_key, 'n2'}
    assert old == unchanged
