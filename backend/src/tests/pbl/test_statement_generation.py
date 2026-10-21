import json
from types import SimpleNamespace
import httpx
import pytest
from app.pbl import project_generator
from app.pbl.project_workflow import PHASE_REFERENCES, load_project_skill
from app.pbl.project_schemas import STARTER_FILES


def model_response(monkeypatch, module, result):
    captured=[]
    gateway=SimpleNamespace(candidates=[{'model_name':'fixture','api_base':'https://model.invalid/v1'}],
                            _thinking_params=lambda _: {}, _build_headers=lambda _: {})
    monkeypatch.setattr(module.runtime_config_resolver,'resolve',lambda *args,**kwargs:{'model':'fixture'})
    monkeypatch.setattr(module.BoundedModelAdapter,'from_config',lambda _:SimpleNamespace(gateway=gateway))
    original=httpx.AsyncClient
    def respond(request):
        captured.append(json.loads(request.content))
        return httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'content':json.dumps(result,ensure_ascii=False)}}]})
    monkeypatch.setattr(module.httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(respond),**kwargs))
    return captured


@pytest.mark.asyncio
@pytest.mark.parametrize('phase',['build_step','repair_step'])
async def test_project_prompt_and_skill_keep_full_statement_separate_from_summary(monkeypatch,phase):
    unit={'stepId':'content','title':'页面内容','objective':'展示内容','instructionsMarkdown':'实现内容','explanationMarkdown':'内容组成','hints':['添加内容'],'focusFiles':['/src/App.jsx'],'checkIds':['content-visible']}
    body='本步要求：保留前面成果。\n\n'+('独特交互边界必须保留。'*45)
    unit['instructionsMarkdown']=body
    result={'unit':unit,'checks':[{'id':unit['checkIds'][0],'label':'显示区','actions':[{'type':'assert','target':{'testId':'display'},'assertion':'visible'}]}],
            'referenceFiles':STARTER_FILES,'faultyFiles':STARTER_FILES,'faultyCheckId':unit['checkIds'][0]}
    from .test_generation import phase_result
    result=phase_result(result,phase)
    captured=model_response(monkeypatch,project_generator,result)
    generated=await project_generator.generate_project_phase('fixture',{},phase,{'step':unit})
    prompt=json.loads(captured[0]['messages'][1]['content'])
    constraints='\n'.join(prompt['runtime']['constraints'])
    assert '完整题目正文' in constraints and 'data-testid' in constraints
    assert 'objective 只作一句话目标' in constraints
    assert '不要把所有项目步骤写成输入输出题' in constraints
    assert '代码约定' in constraints and '不会改变页面外观' in constraints
    assert '全部本步检查项' in constraints
    assert len(captured)==1
    assert '不能省略关键条件' in captured[0]['messages'][0]['content']
    assert generated['unit']['instructionsMarkdown']==body
    assert generated['unit']['objective']==unit['objective']


@pytest.mark.parametrize('phase',list(PHASE_REFERENCES))
def test_loaded_instructions_have_no_project_specific_rules(phase):
    instructions=load_project_skill(phase)['instructions']
    for forbidden in ('计算器','快速排序','quicksort','calculator','testId=display','testId="display"','examples/'):
        assert forbidden not in instructions


@pytest.mark.asyncio
@pytest.mark.parametrize('phase',['plan','review_plan','build_step','repair_step','build_checks','repair_checks'])
@pytest.mark.parametrize('topic',['计算器','快速排序','待办清单','报名表单'])
async def test_provider_gets_same_generic_constraints_for_every_topic(monkeypatch,phase,topic):
    from app.services.durable_task_handlers import DurableTaskExecutionError
    captured=model_response(monkeypatch,project_generator,{'unsupportedGoal':'核心要求不受运行环境支持'})
    with pytest.raises(DurableTaskExecutionError) as error:
        await project_generator.generate_project_phase('fixture',{},phase,{'topic':topic})
    assert error.value.code=='UNSUPPORTED_PROJECT_RUNTIME'
    assert len(captured)==1
    prompt=json.loads(captured[0]['messages'][1]['content'])
    assert prompt['data']=={'topic':topic}
    constraints='\n'.join(prompt['runtime']['constraints'])
    for forbidden in ('计算器','快速排序','quickSort','calculator','testId=display','testId="display"'):
        assert forbidden not in constraints
    assert '不预设固定步骤数或首步类型' in constraints
    assert '不默认强制双窗口' in constraints
    assert '不能把不支持的目标静默替换' in constraints

@pytest.mark.asyncio
async def test_invalid_schema_keeps_raw_candidate_for_repair(monkeypatch):
    rejected={'unit':{'stepId':'incomplete'},'referenceFiles':{'/src/App.jsx':'private unfinished code'}}
    model_response(monkeypatch,project_generator,rejected)
    with pytest.raises(project_generator.InvalidProjectOutput) as error:
        await project_generator.generate_project_phase('fixture',{},'build_step',{})
    assert error.value.raw==rejected


@pytest.mark.asyncio
@pytest.mark.parametrize('passed',[True,False])
async def test_repair_provider_receives_prior_evidence_and_distinguishes_code_regression(monkeypatch,passed):
    from app.services.durable_task_handlers import DurableTaskExecutionError
    captured=model_response(monkeypatch,project_generator,{'unsupportedGoal':'fixture'})
    data={'previousFiles':{'/src/App.jsx':'previous'},
          'priorCandidate':{'referenceFiles':{'/src/App.jsx':'current'}},
          'previousChecks':[{'id':'existing'}],
          'previousCheckReport':{'passed':passed,'results':[{'caseId':'existing','message':'expected original, got changed'}]}}
    with pytest.raises(DurableTaskExecutionError):
        await project_generator.generate_project_phase('fixture',{},'repair_step',data)
    messages=captured[0]['messages']
    assert json.loads(messages[1]['content'])['data']==data
    assert ('当前任务是修复已被浏览器证实的前序回归' in messages[0]['content']) is (not passed)


@pytest.mark.asyncio
async def test_acceptance_schema_binds_current_ids_and_inherits_omitted_unit_fields(monkeypatch):
    unit={'stepId':'content','title':'页面内容','objective':'展示内容','instructionsMarkdown':'实现内容','explanationMarkdown':'内容组成','hints':['添加内容'],'focusFiles':['/src/App.jsx'],'checkIds':['content-visible']}
    result={'type':'json_object','unit':{'instructionsMarkdown':'按实际接口更新约定'},'checks':[{'id':'content-visible','label':'内容可见','actions':[{'type':'assert','target':{'testId':'content'},'assertion':'visible'}]}]}
    captured=model_response(monkeypatch,project_generator,result)
    generated=await project_generator.generate_project_phase('fixture',{},'build_checks',{'unit':unit,'step':{'id':'content','newCheckIds':['content-visible']}})
    schema=json.loads(captured[0]['messages'][1]['content'])['schema']
    assert schema['$defs']['UiCheck']['properties']['id']['enum']==['content-visible']
    assert schema['$defs']['BehaviorCase']['properties']['checkId']['enum']==['content-visible']
    assert schema['$defs']['StepUnit']['properties']['stepId']['const']=='content'
    assert generated['unit']=={**unit,'instructionsMarkdown':'按实际接口更新约定'}
