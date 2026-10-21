import copy
import pytest
from app.pbl import service, project_service, project_generator
from app.pbl.project_schemas import JestCheck, ProjectArtifact, validate_planned_checks
from .test_project_integration import plan, pipeline, artifact
from .test_statement_generation import model_response

def native(cid):
    return {'id':cid,'label':'检查组件行为','engine':'sandpack-jest','source':"import App from '../src/App.jsx'; test('行为',()=>expect(typeof App).toBe('function'));"}

def test_native_and_legacy_artifacts_roundtrip(artifact):
    payload=artifact.model_dump(mode='json')
    payload['checks'][0]=native(payload['checks'][0]['id'])
    parsed=ProjectArtifact.model_validate(payload)
    assert isinstance(parsed.checks[0],JestCheck)
    assert parsed.model_dump(mode='json')['checks'][0]['source']==payload['checks'][0]['source']

def test_normal_assertion_hints_do_not_reject_valid_alternative(plan):
    spec=plan['checks'][0];spec['requiredAssertions']=['text']
    validate_planned_checks(plan,[native(spec['id'])])
    validate_planned_checks(plan,[{'id':spec['id'],'actions':[{'type':'assert','assertion':'count','expected':0}]}])
    spec['requiredAssertions']=['within_viewport']
    with pytest.raises(ValueError,match='布局检查'):validate_planned_checks(plan,[native(spec['id'])])

@pytest.mark.asyncio
async def test_generated_native_checks_preserve_cumulative_context_and_resume(repository,exercise,pipeline,monkeypatch):
    context,calls,_=pipeline
    original=project_service.generate_project_phase
    seen=[]
    async def model(owner,snapshot,phase,data):
        result=await original(owner,snapshot,phase,data)
        if phase in {'build_checks','repair_checks'}:
            seen.append(copy.deepcopy(data))
            result['checks']=[native(cid) for cid in data['step']['newCheckIds']]
        return result
    monkeypatch.setattr(project_service,'generate_project_phase',model)
    publish=repository.publish
    def interrupted(*args,**kwargs): raise RuntimeError('interrupted before publication')
    monkeypatch.setattr(repository,'publish',interrupted)
    with pytest.raises(RuntimeError,match='interrupted before publication'):
        await service.generate_exercise({'exercise_id':exercise.id,'topic':'组件项目'},context,repository=repository)
    checkpoint=repository.get_owned('alice',exercise.id).checkpoint
    assert len(checkpoint['completed'])==4
    assert repository.get_owned('alice',exercise.id).artifact_public is None
    calls.clear()
    monkeypatch.setattr(repository,'publish',publish)
    await service.generate_exercise({'exercise_id':exercise.id,'topic':'组件项目'},context,repository=repository)
    assert not calls  # Saved native candidates are re-executed, not regenerated.
    row=repository.get_owned('alice',exercise.id)
    assert all(c['engine']=='sandpack-jest' for c in row.artifact_public['checks'])
    assert seen[1]['previousChecks'][0]['source']==row.artifact_public['checks'][0]['source']
    assert seen[1]['previousCheckReport']['passed']

@pytest.mark.asyncio
async def test_provider_schema_and_prompt_expose_native_test_semantics(monkeypatch):
    unit={'stepId':'content','title':'页面','objective':'内容','instructionsMarkdown':'实现','explanationMarkdown':'讲解','hints':['提示'],'focusFiles':['/src/App.jsx'],'checkIds':['content']}
    captured=model_response(monkeypatch,project_generator,{'unit':unit,'checks':[native('content')]})
    generated=await project_generator.generate_project_phase('fixture',{},'build_checks',{'unit':unit,'step':{'id':'content','newCheckIds':['content']}})
    assert generated['checks'][0]['engine']=='sandpack-jest'
    assert '@testing-library/react' in captured[0]['messages'][1]['content']
    assert 'hasAssertions' not in generated['checks'][0]['source']  # Host provides execution guard.
