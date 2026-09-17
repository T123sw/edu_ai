import asyncio
from uuid import uuid4
import pytest
from fastapi import HTTPException
from app.database import Base
from app.self_learning.check_service import CheckService, CheckSubmission
from tests.self_learning.test_agent_runtime import agent_service, live_service, repository

@pytest.fixture
def checks(agent_service):
    from app.self_learning.enrichment_models import TABLES
    Base.metadata.create_all(agent_service.session_repository.engine, tables=[Base.metadata.tables[n] for n in TABLES])
    service = CheckService(agent_service, agent_service.session_repository.engine)
    agent_service.checks = service
    agent_service.manager.save_generated_material('course', 'quiz', 'quiz1', {'title': '变量练习', 'questions': [
        {'id': 'q1', 'type': 'single_choice', 'stem': '哪一个是变量赋值？', 'options': ['x = 1', 'print(x)'], 'answer': 'A', 'explanation': '赋值把值绑定给变量。'}], 'learning_course_resource': True},
        owner_user_id='alice', visibility='course', scope_type='knowledge_point', scope_id='a')
    return service

def offer(checks):
    return asyncio.run(checks.offer('alice', 'course', 'a', str(uuid4())))

def submit(checks, check, **kwargs):
    return asyncio.run(checks.submit('alice', check['check_id'], CheckSubmission(request_id=uuid4(), question_version=check['question_version'], **kwargs)))

def test_snapshot_is_public_and_skip_has_no_evidence(checks):
    check = offer(checks)
    assert 'answer' not in str(check['public_question'])
    attempt = submit(checks, check, skipped=True)
    assert attempt['status'] == 'skipped' and attempt['evidence_refs'] == []
    assert checks.get('alice', check['check_id'])['attempts'][0]['attempt_id'] == attempt['attempt_id']

def test_wrong_answer_is_saved_without_changing_completion(checks):
    check = offer(checks)
    attempt = submit(checks, check, option_ids=['option_2'])
    assert attempt['status'] == 'graded' and attempt['correct'] is False
    facts = checks.learning.progress_service.repository.read('alice', 'course')
    assert all(not r.get('completed') for r in facts['resources'])
    assert checks.get('alice', check['check_id'])['attempts'][0]['feedback']

def test_idempotency_version_and_option_validation(checks):
    check = offer(checks)
    req = CheckSubmission(request_id=uuid4(), question_version=1, option_ids=['option_1'])
    first = asyncio.run(checks.submit('alice', check['check_id'], req))
    assert asyncio.run(checks.submit('alice', check['check_id'], req)) == first
    assert first['correct'] is True
    for bad in [req.model_copy(update={'option_ids': ['outside']}), req.model_copy(update={'question_version': 2})]:
        with pytest.raises(HTTPException):
            asyncio.run(checks.submit('alice', check['check_id'], bad))
    with pytest.raises(HTTPException):
        checks.get('bob', check['check_id'])

def test_subjective_failure_keeps_answer(checks):
    async def generator(*_):
        return {'form': 'short_answer', 'stem': '解释变量赋值', 'options': [], 'correct_option_ids': [], 'reference_answer': '值绑定到变量', 'explanation': '关注赋值关系'}
    async def broken(*_):
        raise RuntimeError('model unavailable')
    checks.generator, checks.evaluator = generator, broken
    check = asyncio.run(checks.offer('alice', 'course', 'b', str(uuid4()), preferred_form='short_answer'))
    attempt = submit(checks, check, text='给变量一个值')
    assert attempt['status'] == 'evaluation_failed' and attempt['text'] == '给变量一个值'
    assert attempt['evidence_refs'] == []

def test_reading_version_changes_do_not_regrade_old_attempt(checks):
    check = offer(checks)
    attempt = submit(checks, check, option_ids=['option_1'])
    checks.learning.manager.save_generated_material('course', 'quiz', 'quiz1', {'title':'新版', 'questions':[
        {'stem':'新版问题', 'options':['甲','乙'], 'answer':'B'}], 'learning_course_resource':True},
        owner_user_id='alice', visibility='course', scope_type='knowledge_point', scope_id='a')
    restored = checks.get('alice', check['check_id'])
    assert restored['source_ref']['version'] == 1
    assert restored['attempts'][0] == attempt and attempt['correct'] is True


def test_goal_judgment_requires_versioned_rule_and_independent_questions():
    from app.self_learning.contracts import TopicView, LearningFacts
    from app.self_learning.projections import project_topic
    ref={'course_id':'c','material_type':'report','material_id':'d','version':1}
    topic=TopicView(topic_id='t',title='目标', resources=[{'resource_ref':ref}], objectives=[{'objective_id':'o','text':'解释变量'}])
    item={'attempt_id':'a','check_id':'q','topic_id':'t','objective_ids':['o'],'correct':True,'evaluator':'deterministic','resource_ref':ref,'rule_version':'v1'}
    facts=LearningFacts(check_evidence=[item])
    assert project_topic(topic,facts).judgment == 'unverified'
    topic.objectives[0].check_rule={'version':1,'min_successes':2}
    assert project_topic(topic,facts).judgment == 'unverified'
    facts.check_evidence.append({**item,'attempt_id':'b','check_id':'q2'})
    assert project_topic(topic,facts).judgment == 'evidence_supports'
    facts.check_evidence.append({**item,'attempt_id':'c','check_id':'q3','correct':False})
    assert project_topic(topic,facts).judgment == 'mixed'

def test_offer_tool_replay_recovers_saved_question(checks):
    import json
    from app.self_learning.context_builder import ContextBuilder
    from app.self_learning.tools import LearningTools
    from tests.self_learning.test_agent_runtime import accept
    svc = checks.learning
    first = accept(svc)
    turn = svc.turn_repository.get('alice', first['turn_id'])
    tools = LearningTools(svc, turn, ContextBuilder(svc).build(turn))
    call={'id':'check','type':'function','function':{'name':'offer_understanding_check','arguments':json.dumps({'objective_ids':[]})}}
    one=asyncio.run(tools.dispatch_write(call))
    two=asyncio.run(tools.dispatch_write(call))
    assert one['ok'] and one == two
    assert len(checks.list('alice','course','a')) == 1

def test_manifest_check_maps_objectives_and_required_activity(checks):
    from app.self_learning.contracts import Actor
    svc = checks.learning
    svc.progress_service.repository.evidence_reader = checks.evidence
    svc.progress_service.reader.load_manifest = lambda *_: {'course_id':'course','manifest_id':'m','version':1,'route_version':1,'nodes':[
        {'node_id':'a','title':'变量','objectives':[{'objective_id':'o','text':'理解赋值','check_rule':{'version':1,'min_successes':1}}],
         'required_activity_ids':['manifest-check'], 'resources':[{'resource_type':'quiz','resource_id':'quiz1','version':1,'required':True,'objective_ids':['o']}],
         'checks':[{'check_id':'manifest-check','resource_id':'quiz1','resource_version':1,'objective_ids':['o'],'locator':{'question_id':'q1'}}]}]}
    check = offer(checks)
    assert check['objective_ids'] == ['o']
    submit(checks, check, option_ids=['option_1'])
    projection = svc.progress_service.read(Actor(user_id='alice'),'course')
    assert projection['topics'][0]['judgment'] == 'evidence_supports'
    assert projection['check_evidence'][0]['activity_id'] == 'manifest-check'
    assert projection['topics'][0]['progress'] != 'core_completed'  # checking never marks reading complete

def test_material_quiz_uses_snapshot_ids_and_blocks_legacy_writes(checks):
    first=checks.material_checks('alice','course','quiz1',1)
    replay=checks.material_checks('alice','course','quiz1',1)
    assert first==replay
    check=first['items'][0]
    assert 'correct_option_ids' not in check['public_question']
    result=submit(checks,check,option_ids=['option_1'])
    assert result['correct'] is True
    restored=checks.material_checks('alice','course','quiz1',1)
    assert restored['items'][0]['attempts'][0]['attempt_id']==result['attempt_id']
    with pytest.raises(HTTPException) as old:
        checks.learning.practice('course','alice','quiz1',1,{'q1':'A'})
    assert old.value.status_code==409
    assert not checks.learning.store.get('alice','course').get('practice')

def test_generated_short_answer_keeps_reference(checks):
    question=checks.bank_question({'form':'short_answer','stem':'变量是什么','reference_answer':'变量名绑定值','explanation':'区分名称和值'})
    assert question.reference_answer=='变量名绑定值'
