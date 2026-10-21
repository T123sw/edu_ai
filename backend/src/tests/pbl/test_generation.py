from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
import pytest
from app.pbl import service, project_service, project_validation
from app.pbl.project_schemas import STARTER_FILES
from app.services.durable_task_handlers import DurableTaskExecutionError

@pytest.fixture
def context(exercise):
    return SimpleNamespace(task_id=exercise.current_job_id, owner_user_id='alice',
        progress=Mock(), is_cancel_requested=lambda: False, is_lease_valid=lambda: True,
        lease_owner='worker', attempt_count=1)

@pytest.fixture
def command(exercise):
    return {'exercise_id': exercise.id, 'topic': exercise.topic, 'runtime_config_snapshot': {}}


def phase_result(candidate, phase):
    if phase in {'build_step','repair_step'}:
        return {k:candidate[k] for k in ('unit','referenceFiles')}
    return {k:v for k,v in candidate.items() if k!='referenceFiles'}


def install_pipeline(monkeypatch):
    """Minimal topic-neutral phase and runner doubles for durability tests."""
    plan={'schemaVersion':1,'title':'页面项目','goal':'完成页面成果','runtimeKind':'react_app',
          'editableFiles':list(STARTER_FILES),'requirements':[{'id':'content','description':'页面内容'}],
          'steps':[{'id':'content','title':'完成内容','objective':'展示内容','dependsOn':[],
                    'entryCondition':'初始工程','deliverable':'内容可见','requirementIds':['content'],
                    'focusFiles':list(STARTER_FILES),'newCheckIds':['content-visible']}],
          'checks':[{'id':'content-visible','stepId':'content','kind':'ui_scenario','requirementIds':['content'],
                     'setup':'打开页面','actions':['查看内容'],'expected':['内容可见'],'requiredAssertions':['visible']}]}
    async def generate(owner,snapshot,phase,data):
        if phase=='plan': return plan
        if phase=='review_plan': return {'approved':True,'issues':[]}
        step=plan['steps'][0]
        candidate={'unit':{'stepId':step['id'],'title':step['title'],'objective':step['objective'],
                       'instructionsMarkdown':'完成页面内容。','explanationMarkdown':'理解页面组成。','hints':['添加内容'],
                       'focusFiles':step['focusFiles'],'checkIds':step['newCheckIds']},
                'checks':[{'id':'content-visible','label':'内容可见','actions':[{'type':'assert','target':{'testId':'content'},'assertion':'visible'}]}],
                'referenceFiles':{**STARTER_FILES,'/src/App.jsx':'reference'},'faultyFiles':STARTER_FILES,'faultyCheckId':'content-visible'}
        return phase_result(candidate,phase)
    def check(files,checks):
        passed=files['/src/App.jsx']=='reference'
        return {'passed':passed,'durationMs':1,'results':[{'caseId':c['id'],'status':'passed' if passed else 'failed','message':''} for c in checks]}
    model=AsyncMock(side_effect=generate)
    validation=Mock(side_effect=check)
    monkeypatch.setattr(project_service,'generate_project_phase',model)
    monkeypatch.setattr(project_validation,'check_project',validation)
    return model,validation

@pytest.fixture
def spies(monkeypatch):
    monkeypatch.setattr(service,'get_job',lambda identifier:None)
    return install_pipeline(monkeypatch)

@pytest.mark.asyncio
@pytest.mark.parametrize('topic',['快速排序','Quick Sort exercise','计算器','待办清单','报名表单','文章阅读页'])
async def test_every_unpublished_topic_uses_same_pipeline(repository,command,context,monkeypatch,topic):
    project=AsyncMock(return_value={'saved':True})
    monkeypatch.setattr(service,'get_job',lambda _:None)
    monkeypatch.setattr(project_service,'generate_project',project)
    request={**command,'topic':topic}
    result=await service.generate_exercise(request,context,repository=repository)
    assert result['saved']
    project.assert_awaited_once_with(request,context,repository)

@pytest.mark.asyncio
async def test_generation_publishes_validated_project_and_replays(repository,exercise,command,context,spies):
    await service.generate_exercise(command,context,repository=repository)
    row=repository.get_owned('alice',exercise.id)
    assert row.artifact_public['schemaVersion']==2
    assert 'referenceFiles' not in row.artifact_public
    assert row.candidate_private['completed'][0]['validated']
    assert [call.args[2] for call in spies[0].call_args_list]==['plan','build_step','build_checks']
    before=(spies[0].await_count,spies[1].call_count)
    await service.generate_exercise(command,context,repository=repository)
    assert before==(spies[0].await_count,spies[1].call_count)

@pytest.mark.asyncio
async def test_existing_v1_artifact_is_not_replanned(repository,ready_exercise,command,context,spies):
    before=ready_exercise.artifact_public
    await service.generate_exercise(command,context,repository=repository)
    assert spies[0].await_count==spies[1].call_count==0
    assert repository.get_owned('alice',ready_exercise.id).artifact_public==before

@pytest.mark.asyncio
async def test_model_timeout_preserves_state(repository,exercise,command,context,spies):
    spies[0].side_effect=TimeoutError('private URL credential')
    with pytest.raises(DurableTaskExecutionError) as error:
        await service.generate_exercise(command,context,repository=repository)
    assert error.value.code=='PBL_MODEL_UNAVAILABLE' and 'credential' not in str(error.value)
    assert repository.get_owned('alice',exercise.id).checkpoint['stage']=='model_failed'

@pytest.mark.asyncio
async def test_cancel_after_model_prevents_validation_and_publication(repository,exercise,command,context,spies):
    original=spies[0].side_effect
    async def generate(*args,**kwargs):
        result=await original(*args,**kwargs)
        context.is_cancel_requested=lambda:True
        return result
    spies[0].side_effect=generate
    with pytest.raises(DurableTaskExecutionError) as error:
        await service.generate_exercise(command,context,repository=repository)
    assert error.value.code=='GENERATION_CANCELLED'
    assert spies[1].call_count==0 and repository.get_owned('alice',exercise.id).artifact_public is None
