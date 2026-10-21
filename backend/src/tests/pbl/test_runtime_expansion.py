import copy
from uuid import uuid4
import pytest
from app.pbl.project_schemas import ProjectArtifact, ProjectCheckRequest, HttpCheck, validate_runtime_plan
from app.pbl.runtime_config import MULTI_TEMPLATE, ProjectRuntime, validate_files
from .test_project_integration import plan, artifact

@pytest.fixture
def multi(artifact):
    value=artifact.model_dump(mode='json')
    runtime={'template':'react','entry':'/index.js','dependencies':{},'moduleType':'commonjs'}
    value.update(runtimeKind='sandpack_project',runtime=runtime,templateVersion=MULTI_TEMPLATE)
    value['plan'].update(runtimeKind='sandpack_project',runtime=runtime)
    value['plan']['editableFiles'].append('/index.js')
    value['starterFiles']['/index.js']="import App from './src/App.jsx';"
    return ProjectArtifact.model_validate(value)

@pytest.mark.parametrize('path',['/../secret.js','/src/../../secret.js','//evil.js','/package.json','/__checks__/fake.test.js','/node_modules/react/index.js','/pblruntime.cjs','/src\\bad.js','/.env','/foo.sh'])
def test_reserved_and_escaping_paths_rejected(path):
    with pytest.raises(ValueError):validate_files({path:''})

@pytest.mark.parametrize('template',['react','react-ts','vanilla','vanilla-ts','vue','svelte','static','node'])
def test_plan_keeps_template_and_multifile_contract(plan,template):
    value=copy.deepcopy(plan)
    value.update(runtimeKind='sandpack_project',runtime={'template':template,'entry':'/src/App.jsx','dependencies':{}})
    value['editableFiles'].append('/src/lib/math.js')
    assert validate_runtime_plan(value)['plan']['runtime']['template']==template

@pytest.mark.parametrize('dependencies',[{'express':'latest'},{'bad':'file:/etc'},{'bad':'https://example.com/a.js'},{'../bad':'1.0.0'}])
def test_dependencies_are_explicit_packages(dependencies):
    with pytest.raises(ValueError):ProjectRuntime(template='node',entry='/server.js',dependencies=dependencies)

def test_new_artifact_requires_matching_runtime_and_files(multi):
    value=multi.model_dump(mode='json')
    value['runtime']['entry']='/other.js'
    with pytest.raises(ValueError):ProjectArtifact.model_validate(value)
    value=multi.model_dump(mode='json');value['starterFiles'].pop('/index.js')
    with pytest.raises(ValueError):ProjectArtifact.model_validate(value)


def test_multifile_workspace_run_versions_and_idempotency(repository,exercise,multi):
    repository.publish('alice',exercise.id,exercise.current_job_id,multi,{},dict(passed=True,templateVersion=MULTI_TEMPLATE,validatedSteps=len(multi.tasks),results=[])|{'results':[{'caseId':c.id,'status':'passed'} for c in multi.checks]})
    workspace=repository.get_or_create_workspace('alice',exercise.id)
    assert workspace.files==multi.starterFiles
    payload={'artifactVersion':1,'taskId':multi.tasks[0].id,'runId':str(uuid4()),'files':workspace.files}
    request,checks,existing=repository.project_check_input('alice',exercise.id,payload)
    result={'passed':True,'durationMs':1,'results':[{'caseId':c['id'],'status':'passed','message':'actual execution'} for c in checks]}
    report=repository.save_project_check('alice',exercise.id,request,result)
    assert report['templateVersion']==MULTI_TEMPLATE
    assert repository.project_check_input('alice',exercise.id,payload)[2]==report
    with pytest.raises(ValueError):repository.project_check_input('alice',exercise.id,{**payload,'runId':str(uuid4()),'files':{'/src/App.jsx':''}})

@pytest.mark.parametrize('path',['//other.test/a','/\\other.test/a','http://localhost/a'])
def test_http_targets_cannot_change_origin(path):
    with pytest.raises(ValueError):HttpCheck(id='http',label='API',engine='http',requests=[dict(path=path,status=200)])

@pytest.mark.asyncio
@pytest.mark.parametrize('template,allowed',[('vue',{'UiCheck'}),('svelte',{'UiCheck'}),('node',{'UiCheck','HttpCheck'}),('react-ts',{'UiCheck','JestCheck'}),('vanilla',{'UiCheck'})])
async def test_model_receives_only_selected_runtime_and_supported_checks(monkeypatch,template,allowed):
    import json
    from app.pbl import project_generator
    from .test_statement_generation import model_response
    unit={'stepId':'content','title':'页面','objective':'内容','instructionsMarkdown':'实现','explanationMarkdown':'讲解','hints':['提示'],'focusFiles':['/index.js'],'checkIds':['content']}
    check={'id':'content','label':'内容','actions':[{'type':'assert','target':{'role':'main'},'assertion':'visible'}]}
    captured=model_response(monkeypatch,project_generator,{'data':{'unit':unit,'checks':[check]}})
    await project_generator.generate_project_phase('fixture',{},'build_checks',{'unit':unit,'plan':{'runtime':{'template':template}},'step':{'id':'content','newCheckIds':['content']}})
    prompt=json.loads(captured[0]['messages'][1]['content'])
    assert set(prompt['runtime']['templates'])=={template}
    assert {item['$ref'].split('/')[-1] for item in prompt['schema']['properties']['checks']['items']['anyOf']}==allowed


def test_http_body_limit_is_explicit_capability_failure():
    with pytest.raises(ValueError):HttpCheck(id='body',label='写入',engine='http',requests=[dict(path='/notes',method='POST',body={'text':'hello'},status=201)])


def test_source_json_can_contain_literal_newlines_without_guessing_structure():
    from app.pbl.project_generator import project_answer_json
    assert project_answer_json('{"source":"first\nsecond\tvalue"}')=={'source':'first\nsecond\tvalue'}
    with pytest.raises(ValueError):project_answer_json('{"source":"first\nsecond","source":"other"}')
    with pytest.raises(ValueError):project_answer_json('{"source":"missing end}')


def test_unstable_template_is_not_offered_to_generation():
    from app.pbl.runtime_config import capabilities
    assert 'vue-ts' not in capabilities()
    with pytest.raises(ValueError):ProjectRuntime(template='vue-ts',entry='/src/main.ts')


@pytest.mark.asyncio
async def test_wrapped_unsupported_goal_stops_without_plan_repair(monkeypatch):
    from app.pbl import project_generator
    from app.services.durable_task_handlers import DurableTaskExecutionError
    from .test_statement_generation import model_response
    model_response(monkeypatch,project_generator,{'data':{'unsupportedGoal':'需要 HTTP 请求体'}})
    with pytest.raises(DurableTaskExecutionError,match='请求体'):
        await project_generator.generate_project_phase('fixture',{},'plan',{'topic':'HTTP API'})
