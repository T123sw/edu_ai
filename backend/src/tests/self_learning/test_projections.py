import pytest

from app.self_learning.contracts import CourseView, LearningFacts, ResourceRef, ResourceState, TopicView
from app.self_learning.projections import next_actions, project_topic


@pytest.fixture
def topic():
    return TopicView(topic_id='a', title='变量', completion_policy='explicit', resources=[
        {'resource_ref': {'course_id': 'course', 'material_type': 'report', 'material_id': 'core', 'version': 1}, 'required': True, 'title': '核心'},
        {'resource_ref': {'course_id': 'course', 'material_type': 'report', 'material_id': 'extra', 'version': 1}, 'required': False, 'title': '补充'},
    ])


def facts(topic, **state):
    return LearningFacts(resources=[ResourceState(resource_ref=topic.resources[0].resource_ref, **state)])


def test_completion_does_not_imply_understanding(topic):
    result = project_topic(topic, facts(topic, completed=True))
    assert result.progress == 'core_completed'
    assert result.judgment == 'unverified'
    assert result.completed_core == result.total_core == 1


def test_end_reached_is_only_reading_fact(topic):
    result = project_topic(topic, facts(topic, reached_end=True))
    assert result.progress == 'in_progress'
    assert result.completed_core == 0


def test_old_version_does_not_complete_current_resource(topic):
    old = topic.resources[0].resource_ref
    state = ResourceState(resource_ref=old, completed=True)
    topic.resources[0].resource_ref = ResourceRef(**{**old.model_dump(), 'version': 2})
    assert project_topic(topic, LearningFacts(resources=[state])).progress == 'not_started'


def test_unknown_or_empty_core_never_auto_completes(topic):
    topic.completion_policy = 'unknown'
    assert project_topic(topic, facts(topic, completed=True)).progress != 'core_completed'
    topic.completion_policy = 'explicit'
    topic.resources = []
    assert project_topic(topic, LearningFacts()).progress == 'not_started'


def test_self_assessment_is_not_evidence(topic):
    result = project_topic(topic, LearningFacts(self_assessments={'a': 'understood'}))
    assert result.self_assessment == 'understood'
    assert result.judgment == 'unverified'


def test_continue_skips_optional_and_no_checks_are_fabricated(topic):
    other = TopicView(topic_id='b', title='条件', resources=[{
        'resource_ref': {'course_id': 'course', 'material_type': 'report', 'material_id': 'next', 'version': 1}, 'required': True}])
    course = CourseView(course_id='course', source='legacy', topics=[topic, other])
    actions = next_actions(course, facts(topic, completed=True), 'a')
    assert any(a.kind == 'continue' and a.topic_id == 'b' for a in actions)
    assert not any(a.kind == 'check' for a in actions)


def test_unresolved_issue_never_removes_continue(topic):
    course = CourseView(course_id='course', source='legacy', topics=[topic])
    state = LearningFacts(open_questions={'a': ['q1']})
    actions = next_actions(course, state, 'a')
    assert actions[0].kind == 'resolve_question'
    assert any(a.kind == 'continue' for a in actions)


def test_evidence_is_version_bound_and_requires_all_objectives(topic):
    from app.self_learning.contracts import ObjectiveView
    topic=topic.model_copy(update={'objectives':[ObjectiveView(objective_id='o1',text='解释'),ObjectiveView(objective_id='o2',text='应用')]})
    ref=topic.resources[0].resource_ref
    evidence={'evidence_ref':'attempt:1','topic_id':topic.topic_id,'resource_ref':ref,'objective_ids':['o1'],'correct':True,'evaluation_method':'deterministic'}
    assert project_topic(topic,LearningFacts(check_evidence=[evidence])).judgment=='unverified'
    evidence['objective_ids']=['o1','o2']
    assert project_topic(topic,LearningFacts(check_evidence=[evidence])).judgment=='evidence_supports'
    evidence['resource_ref']=ref.model_copy(update={'version':99})
    assert project_topic(topic,LearningFacts(check_evidence=[evidence])).judgment=='unverified'
