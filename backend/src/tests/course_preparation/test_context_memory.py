from uuid import uuid4
import pytest
from app.course_preparation.context import context_packet
from app.course_preparation.research_agent import ResearchError
from app.course_preparation.working_memory import update_working_memory, structural_summary
from app.course_preparation.lifecycle_repository import LifecycleRepository, RevisionConflict
from app.course_preparation.schemas import PreparationRequest


def test_context_counts_tools_and_keeps_hard_request():
    context={'phase':'intent','request':{'goal':'中文学习目标'},'trace':[{'text':'旧历史'*1000}]*12}
    result=context_packet(context,[],max_tokens=20000)
    assert '中文学习目标' in result['messages'][1]['content']
    assert result['role_version'].startswith('research-role.md:')
    with pytest.raises(ResearchError): context_packet(context,[{'schema':'x'*30000}],max_tokens=20000)


def test_working_memory_cas_rejects_facts_and_empty_patches(runtime_engine):
    class Auth:
        def authorize(self,*args): pass
    repo=LifecycleRepository(runtime_engine,authorizer=Auth())
    task=repo.submit('alice',PreparationRequest(request_id=uuid4(),operation='create_course',goal='准备面试'))
    ctx=repo.claim('worker',preparation_id=task['preparation_id'])
    updated=update_working_memory(repo,ctx,{'assumptions':['假设已有 Python 基础']},expected_revision=0)
    assert updated.revision==1
    with pytest.raises(RevisionConflict): update_working_memory(repo,ctx,{},expected_revision=0)
    with pytest.raises(ValueError): update_working_memory(repo,ctx,{},expected_revision=1)
    with pytest.raises(ValueError): update_working_memory(repo,ctx,{'user_facts':['已掌握']},expected_revision=1)
    assert structural_summary({'brief':{'goal':'面试'},'secret':'no'})=={'brief':{'goal':'面试'}}
