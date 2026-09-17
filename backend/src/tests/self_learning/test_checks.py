from uuid import uuid4
import pytest
from fastapi import HTTPException
from app.database import Base
from app.self_learning.check_service import CheckService
from tests.self_learning.test_session_api import live_service,repository


@pytest.fixture
def checks(live_service):
    svc=live_service
    Base.metadata.create_all(svc.session_repository.engine,tables=[Base.metadata.tables[n] for n in ('learning_checks','learning_check_attempts')])
    svc.manager.save_generated_material('course','quiz','quiz-a',{'title':'工具调用检查','version':1,
        'questions':[{'id':'q1','type':'single_choice','stem':'谁执行工具？','options':['模型服务端程序','任意文本'],'answer':'A','explanation':'服务端执行已授权工具。'},
                     {'id':'q2','type':'short_answer','stem':'解释职责划分','answer':'模型选择，服务端执行。'}],
        'learning_course_resource':True},scope_type='knowledge_point',scope_id='a',owner_user_id='alice',visibility='private')
    return CheckService(svc,svc.session_repository.engine)


def offer(checks,question='q1'):
    return checks.offer('alice','course','a',{'course_id':'course','material_type':'quiz','material_id':'quiz-a','version':1},question)


def test_check_hides_answer_invalid_options_are_rejected_and_attempt_is_idempotent(checks):
    check=offer(checks)
    assert 'scoring_key' not in check and 'answer' not in check and 'rubric' not in check
    with pytest.raises(HTTPException): checks.submit('alice',check['check_id'],uuid4(),{'selected_option_id':'outside'})
    assert checks.attempts('alice',check['check_id'])==[]
    rid=uuid4()
    answer={'selected_option_id':'opt-1'}
    first=checks.submit('alice',check['check_id'],rid,answer)
    assert first['correct'] is True and first['evidence_ref']
    assert checks.submit('alice',check['check_id'],rid,answer)==first
    assert len(checks.attempts('alice',check['check_id']))==1
    with pytest.raises(HTTPException): checks.attempts('bob',check['check_id'])


def test_skip_and_wrong_answer_do_not_complete_resource_or_block_navigation(checks):
    check=offer(checks)
    skipped=checks.submit('alice',check['check_id'],uuid4(),{},skip=True)
    assert skipped['correct'] is None and skipped['evidence_ref'] is None
    wrong=checks.submit('alice',check['check_id'],uuid4(),{'selected_option_id':'opt-2'})
    assert wrong['correct'] is False
    assert checks.learning.room('course','alice')['progress']=={}
    assert checks.learning.sessions.enter('alice','course','b')['session_id']


def test_open_answer_is_saved_without_fabricated_grade(checks):
    check=offer(checks,'q2')
    answer=checks.submit('alice',check['check_id'],uuid4(),{'text':'模型提出调用，程序执行并返回结果'})
    assert answer['status']=='pending_review' and answer['correct'] is None
    assert checks.attempts('alice',check['check_id'])[0]['answer']['text'].startswith('模型')


@pytest.mark.asyncio
async def test_evaluation_failure_preserves_answer_and_retry_is_idempotent(checks):
    check=offer(checks,'q2'); rid=uuid4()
    checks.submit('alice',check['check_id'],rid,{'text':'模型选择工具，服务端执行'})
    class Failed:
        async def complete(self,*args,**kwargs): raise TimeoutError()
    failed=await checks.evaluate('alice',check['check_id'],rid,model=Failed())
    assert failed['status']=='pending_review' and failed['evidence_ref'] is None
    assert failed['answer']['text']=='模型选择工具，服务端执行'
    class Good:
        calls=0
        async def complete(self,messages,tools,**kwargs):
            self.calls+=1; assert tools==[]
            return {'content':'{"correct":true,"feedback":"职责划分正确"}','calls':[]}
    good=Good()
    result=await checks.evaluate('alice',check['check_id'],rid,model=good)
    assert result['correct'] is True and result['evaluation_method']=='model'
    assert await checks.evaluate('alice',check['check_id'],rid,model=good)==result
    assert good.calls==1 and len(checks.attempts('alice',check['check_id']))==1
