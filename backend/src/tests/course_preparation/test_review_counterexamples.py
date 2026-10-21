"""Regression controls; opt-in real-model checks are explicitly separate."""
import copy
import json
import os
from types import SimpleNamespace

import pytest
from app.chat.harness.reviewed_report import generate_reviewed_report, verified_review
from app.chat.harness.reviewed_resource import ReviewedResourceGenerator, review_content, verified_resource
from tests.chat.test_reviewed_report import BODY, payload as report_payload, review
from tests.course_preparation.test_generated_content_constraints import quiz_envelope, completion_review
from tests.course_preparation.test_generation_adapter import generation, submit

COUNTEREXAMPLE = {
    'option_text': '模型和程序都负责执行工具，只是先后顺序不同',
    'explanation': '该选项错误地认为程序也参与工具选择',
    'expected': 'reject_explanation_mismatch',
}


def counterexample():
    return {'questions':[{'id':'q-tool-roles', 'type':'single_choice', 'stem':'工具调用中模型与程序的职责是什么？',
        'options':['模型提出工具名与参数，程序校验并执行',COUNTEREXAMPLE['option_text']], 'answer':'A',
        'explanation':'A 正确，模型提出请求，程序执行。B 错误，'+COUNTEREXAMPLE['explanation']+'。'}]}


def rejection(reason, *, answer=True, option_valid=False):
    response=review(True)
    response['question_checks']=[{'question_index':0,'independent_solution':reason,'answer_matches':answer,
        'explanation_valid':option_valid,'option_checks':[
            {'option_index':0,'independent_correct':True,'explanation_reasoning':'已独立逐句检查解析中的主张是否对应原选项。', 'explanation_excerpt':'A 正确，模型提出请求，程序执行。','reasoning':'模型提出请求，程序执行工具','explanation_valid':True},
            {'option_index':1,'independent_correct':False,'explanation_reasoning':reason, 'explanation_excerpt':COUNTEREXAMPLE['explanation'],'reasoning':reason,'explanation_valid':option_valid}]}]
    return response


class ConstantGateway:
    def __init__(self,response): self.response=response
    def chat(self,*args,**kwargs): return json.dumps(self.response,ensure_ascii=False)


def test_real_audit_counterexample_is_rejected_even_if_answer_is_correct():
    response=rejection('B 声称双方都执行，没有声称程序选择工具，原解析指向不存在的主张。')
    checked,feedback=review_content('quiz',counterexample(),{},ConstantGateway(response))
    assert feedback and checked.question_checks[0].answer_matches
    option=checked.question_checks[0].option_checks[1]
    assert option.option_text==COUNTEREXAMPLE['option_text']
    assert option.explanation_excerpt==COUNTEREXAMPLE['explanation']
    assert not option.explanation_valid


@pytest.mark.parametrize('defect',['wrong_answer','ambiguous_multiple','missing_explanation','outside_objectives'])
def test_minimal_quiz_failures_are_not_silently_approved(defect):
    from app.chat.harness.reviewed_resource import validate_resource
    content=counterexample()
    reason={'wrong_answer':'独立判断A成立，给出的B答案错误。',
        'ambiguous_multiple':'题干未明确假设，无法确定唯一的多选范围。',
        'outside_objectives':'题目要求操作系统调度知识，超出工具调用节点的目标。',
        'missing_explanation':'缺少解析。'}[defect]
    if defect=='missing_explanation':
        content['questions'][0]['explanation']=''
        with pytest.raises(ValueError): validate_resource('quiz',content)
        return
    if defect=='wrong_answer': content['questions'][0]['answer']='B'
    if defect=='ambiguous_multiple':
        content['questions'][0].update(type='multiple_choice',stem='在一些实现中哪些角色可能执行或委托工具？')
    if defect=='outside_objectives': content['questions'][0]['stem']='操作系统如何调度进程？'
    response=rejection(reason,answer=False)
    response['blocking_issues']=[reason]
    _,feedback=review_content('quiz',content,{'teaching_context':{'objectives':['解释工具调用职责']}},ConstantGateway(response))
    assert reason in feedback


@pytest.mark.parametrize('field,value',[('option_text','程序选择工具'),('explanation_excerpt','原文不存在的解释')])
def test_review_cannot_bind_to_a_different_option_or_invent_an_excerpt(field,value):
    response=rejection('选项说的是执行，而原解析误解为工具选择。')
    response['question_checks'][0]['option_checks'][1][field]=value
    with pytest.raises(ValueError,match='mismatch'):
        review_content('quiz',counterexample(),{},ConstantGateway(response))


@pytest.mark.parametrize('kind',['report','quiz'])
def test_process_retry_uses_actual_private_checkpoint_without_rewriting(generation,kind):
    checkpoint_module=pytest.importorskip('app.course_preparation.resource_checkpoint')
    failures=pytest.importorskip('app.course_preparation.generation_failures')
    repo,parent,adapter=generation
    _,receipt=submit(generation)
    child=adapter.artifacts.claim('alice',receipt['artifact_id'])
    port=checkpoint_module.ArtifactResourceCheckpoint(adapter.artifacts,child)
    calls={'writer':0,'review':0}
    class Gateway:
        def chat(self,messages,**kwargs):
            data=json.loads(messages[-1]['content'])
            if 'schema' in data:
                calls['review']+=1
                return '{}' if calls['review']==1 else json.dumps(completion_review(data,kind))
            calls['writer']+=1
            return BODY if kind=='report' else json.dumps(quiz_envelope()['content'])
    gateway=Gateway()
    value=report_payload() if kind=='report' else SimpleNamespace(resource_type='quiz',title='工具调用')
    value.spec_digest=child['spec_digest']
    def run(checkpoint):
        if kind=='report':
            body,state=generate_reviewed_report(value,gateway,checkpoint=checkpoint)
            return {'content':body,'generation_state':state}
        return ReviewedResourceGenerator(gateway,checkpoint=checkpoint).generate(value,job_id='j',config_snapshot_id='c')['artifacts'][0]
    with pytest.raises(failures.GenerationFailure) as error:
        run(port)
    assert error.value.detail.category=='review_format'
    assert error.value.detail.retry_scope=='review'
    saved=port.load_review_candidate()
    before=saved['content_digest']
    assert error.value.detail.content_digest==before
    # Persist failure and exercise F's real retry/lease transition before a
    # fresh store/port loads the same SQL candidate.
    from app.course_preparation.artifact_store import ArtifactStore
    adapter.artifacts.fail(child,error.value.detail)
    recovered=ArtifactStore(repo)
    recovery=recovered.resume_review(parent,child['artifact_id'],recovery_key='d-review-retry')
    assert recovery['retry_scope']=='review'
    next_child=recovered.claim('alice',child['artifact_id'])
    assert next_child['lease_token']!=child['lease_token']
    new_port=checkpoint_module.ArtifactResourceCheckpoint(recovered,next_child)
    final=run(new_port)
    assert calls=={'writer':1,'review':2}
    assert new_port.load_review_candidate()['content_digest']==before
    assert verified_review(final) if kind=='report' else verified_resource(final,kind)
    assert adapter.artifacts.get('alice',receipt['artifact_id'])['status']=='running'


@pytest.mark.skipif(os.getenv('D_CONTENT_REAL_MODEL')!='1',reason='opt-in real model quality check; separate from scripted gateway tests')
def test_real_model_recognizes_non_arithmetic_explanation_mismatch():
    import dotenv
    from app.chat.model_gateway import ChatModelGateway
    settings=dotenv.dotenv_values(os.environ['D_CONTENT_ENV_FILE'])
    gateway=ChatModelGateway(api_base=settings['DEEPSEEK_BASE_URL'],api_key=settings['DEEPSEEK_API_KEY'],
        model_name=settings.get('LLM_MODEL') or 'deepseek-v4-pro')
    checked,feedback=review_content('quiz',counterexample(),{'objectives':['区分模型提出调用与程序执行']},gateway)
    assert feedback and not checked.question_checks[0].option_checks[1].explanation_valid
    evidence=os.getenv('D_CONTENT_EVIDENCE_FILE')
    if evidence:
        from pathlib import Path
        Path(evidence).write_text(json.dumps({'scope':'real model semantic review; not native Harness integration',
            'content':counterexample(),'review':checked.model_dump(),'feedback':feedback},ensure_ascii=False,indent=2))


def _claim_checkpoint(generation, kind):
    from app.course_preparation.resource_checkpoint import ArtifactResourceCheckpoint
    from app.course_preparation.runtime_contracts import BudgetCost
    from tests.course_preparation.test_generation_adapter import spec

    repo, parent, adapter = generation
    specification = {**spec(), 'resource_type': kind}
    action = repo.begin_action(parent, 'checkpoint-' + kind, 'generate_resource', specification, BudgetCost(calls=1))
    receipt = adapter.submit(parent, specification, action['action_id'])
    child = adapter.artifacts.claim('alice', receipt['artifact_id'])
    return adapter, child, ArtifactResourceCheckpoint(adapter.artifacts, child)


def test_classroom_saved_candidate_requires_no_model_review_or_repair(generation):
    from app.chat.harness.reviewed_resource import review_classroom
    from tests.course_preparation.legacy_classroom_fixtures import TeachingScript, native_classroom
    from app.chat.harness.preparation_content import value_digest
    adapter, child, port = _claim_checkpoint(generation, 'classroom')
    original = native_classroom(TeachingScript(slides=[{
        'title': '工具调用', 'points': ['模型提出，程序执行'],
        'narration': '模型提出调用，程序校验权限和参数后执行。' * 6,
    } for _ in range(2)]), '课堂', child['resource_id'])
    port.save_review_candidate(content=original, content_digest=value_digest(original),
        spec_digest=child['spec_digest'], review_state={})
    class NoModel:
        def chat(self, *args, **kwargs): raise AssertionError('classroom review must not call a model')
    content, audit = review_classroom(copy.deepcopy(original), {}, gateway=NoModel(), checkpoint=port)
    assert content == original and audit['decision'] == 'skipped'
    assert verified_resource({**content, 'generation_state': {'resource_review': audit}}, 'classroom')
    assert port.load_review_candidate()['content'] == original
    assert adapter.artifacts.get('alice', child['artifact_id'])['status'] == 'running'


def test_quiz_distractor_explanation_exact_repair_is_independently_reviewed():
    from app.chat.harness.reviewed_resource import digest

    original = counterexample()
    original['questions'].append(copy.deepcopy(quiz_envelope()['content']['questions'][0]))
    replacement = 'A 正确，模型提出请求，程序执行。B 错误，模型只提出调用，程序负责执行，二者不是都执行工具。'
    writer_calls, reviewed_contents = [], []

    class Writer:
        def chat(self, messages, **kwargs):
            data = json.loads(messages[-1]['content'])
            assert 'schema' not in data
            writer_calls.append(copy.deepcopy(data))
            if len(writer_calls) == 1:
                return json.dumps(original, ensure_ascii=False)
            assert len(writer_calls) == 2
            assert data['previous_draft'] == original
            assert any('不存在的主张' in item for item in data['feedback'])
            return json.dumps({'edits': [{
                'path': ['questions', 0, 'explanation'],
                'before': original['questions'][0]['explanation'], 'after': replacement,
            }]}, ensure_ascii=False)

    class Reviewer:
        def chat(self, messages, **kwargs):
            data = json.loads(messages[-1]['content'])
            assert 'schema' in data
            reviewed_contents.append(copy.deepcopy(data['content']))
            passed = len(reviewed_contents) == 2
            assert len(reviewed_contents) <= 2
            reason = ('B 声称双方都执行，没有声称程序选择工具，原解析指向不存在的主张。'
                      if not passed else '模型提出调用而程序执行，修正后的解析准确驳斥双方都执行的主张。')
            response = rejection(reason, option_valid=passed)
            if passed:
                assert data['content']['questions'][0]['explanation'] == replacement
                response['question_checks'][0]['option_checks'][1]['explanation_excerpt'] = 'B 错误，模型只提出调用，程序负责执行，二者不是都执行工具。'
            unaffected = completion_review({}, 'quiz')['question_checks'][0]
            unaffected['question_index'] = 1
            response['question_checks'].append(unaffected)
            return json.dumps(response, ensure_ascii=False)

    artifact = ReviewedResourceGenerator(Writer(), review_gateway=Reviewer()).generate(
        SimpleNamespace(resource_type='quiz', title='工具调用'), job_id='quiz-repair', config_snapshot_id='cfg'
    )['artifacts'][0]
    expected = copy.deepcopy(original)
    expected['questions'][0]['explanation'] = replacement
    assert artifact['content'] == expected
    assert reviewed_contents == [original, expected]
    assert len(writer_calls) == 2
    assert [q['id'] for q in artifact['content']['questions']] == [q['id'] for q in original['questions']]
    assert artifact['content']['questions'][1] == original['questions'][1]
    audit = artifact['generation_state']['resource_review']
    assert [item['decision'] for item in audit['history']] == ['revise', 'pass']
    assert [item['content_sha256'] for item in audit['history']] == [digest('quiz', original), digest('quiz', expected)]
    assert verified_resource(artifact, 'quiz')
    assert not verified_resource({**artifact, 'content': original}, 'quiz')


@pytest.mark.parametrize('mutation', ['content', 'content_digest', 'spec_digest', 'persisted_spec'])
def test_actual_private_checkpoint_rejects_candidate_tampering_before_generation(generation, mutation):
    from sqlalchemy.orm import Session
    from app.database.models import PreparationArtifact
    from app.chat.harness.preparation_content import value_digest
    from app.course_preparation.resource_checkpoint import ArtifactResourceCheckpoint

    adapter, child, port = _claim_checkpoint(generation, 'quiz')
    content = quiz_envelope()['content']
    port.save_review_candidate(content=content, content_digest=value_digest(content),
        spec_digest=child['spec_digest'], review_state={'version': 1, 'history': []})
    with Session(adapter.artifacts.engine) as session, session.begin():
        row = session.get(PreparationArtifact, child['artifact_id'])
        stored = copy.deepcopy(row.content)
        if mutation == 'persisted_spec':
            row.spec = {**row.spec, 'title': '篡改后的规格'}
        elif mutation == 'content':
            stored['_review_candidate']['content']['questions'][0]['answer'] = 'B'
        else:
            stored['_review_candidate'][mutation] = '0' * 64
        row.content = stored

    class NoCallsGateway:
        def chat(self, *args, **kwargs):
            pytest.fail('Tampered candidate must be rejected before writing or reviewing')

    new_port = ArtifactResourceCheckpoint(adapter.artifacts, child)
    with pytest.raises(ValueError, match='REVIEW_CANDIDATE_STALE'):
        ReviewedResourceGenerator(NoCallsGateway(), checkpoint=new_port).generate(
            SimpleNamespace(resource_type='quiz', title='工具调用', spec_digest=child['spec_digest']),
            job_id='tampered', config_snapshot_id='cfg')
    assert adapter.artifacts.get('alice', child['artifact_id'])['status'] == 'running'


def test_report_review_resume_in_a_separate_python_process(generation,tmp_path):
    import subprocess
    import sys
    from app.course_preparation.generation_failures import GenerationFailure
    repo,parent,adapter=generation
    if repo.engine.dialect.name!='sqlite':
        pytest.skip('subprocess smoke uses an isolated SQLite file; SQL fencing is parametrized separately')
    _,receipt=submit(generation)
    child=adapter.artifacts.claim('alice',receipt['artifact_id'])
    port=adapter.artifacts.checkpoint_port(child)
    value=report_payload();value.spec_digest=child['spec_digest']
    calls={'writer':0,'review':0}
    class FirstProcessGateway:
        def chat(self,messages,**kwargs):
            if 'schema' in json.loads(messages[-1]['content']):
                calls['review']+=1;return '{}'
            calls['writer']+=1;return BODY
    with pytest.raises(GenerationFailure) as error:
        generate_reviewed_report(value,FirstProcessGateway(),checkpoint=port)
    before=port.load_review_candidate()['content_digest']
    adapter.artifacts.fail(child,error.value.detail)
    adapter.artifacts.resume_review(parent,child['artifact_id'],recovery_key='d-process-retry')
    output=tmp_path/'child-review.json'
    script=r'''
import json,sys
from pathlib import Path
import dotenv
dotenv.load_dotenv=lambda *a,**k:False
from sqlalchemy import create_engine
from app.course_preparation.lifecycle_repository import LifecycleRepository
from app.course_preparation.artifact_store import ArtifactStore
from app.chat.harness.reviewed_report import generate_reviewed_report,verified_review
from tests.chat.test_reviewed_report import payload,review
args=json.loads(sys.stdin.read())
class Auth:
    def authorize(self,*args):pass
store=ArtifactStore(LifecycleRepository(create_engine(args['database']),authorizer=Auth()))
child=store.claim('alice',args['artifact_id'])
port=store.checkpoint_port(child)
value=payload();value.spec_digest=child['spec_digest']
class Gateway:
    writer_calls=0
    review_calls=0
    def chat(self,messages,**kwargs):
        if 'schema' not in json.loads(messages[-1]['content']):
            self.writer_calls+=1
            raise AssertionError('writer must not run in recovered process')
        self.review_calls+=1
        return json.dumps(review(True))
gateway=Gateway()
body,state=generate_reviewed_report(value,gateway,checkpoint=port)
Path(args['output']).write_text(json.dumps({'writer':gateway.writer_calls,'review':gateway.review_calls,
    'digest':port.load_review_candidate()['content_digest'],'verified':verified_review({'content':body,'generation_state':state})}))
'''
    result=subprocess.run([sys.executable,'-c',script],input=json.dumps({'database':str(repo.engine.url),
        'artifact_id':child['artifact_id'],'output':str(output)}),text=True,capture_output=True,timeout=60)
    assert result.returncode==0,result.stderr
    final=json.loads(output.read_text())
    assert calls['writer']+final['writer']==1
    assert calls['review']+final['review']==2
    assert final['digest']==before and final['verified']


@pytest.mark.parametrize('kind',['report','quiz'])
def test_review_only_retry_escalates_semantic_error_before_writing(generation,kind):
    from app.course_preparation.generation_failures import GenerationFailure
    repo,parent,adapter=generation
    _,receipt=submit(generation)
    child=adapter.artifacts.claim('alice',receipt['artifact_id'])
    port=adapter.artifacts.checkpoint_port(child)
    value=report_payload() if kind=='report' else SimpleNamespace(resource_type='quiz',title='工具调用')
    value.spec_digest=child['spec_digest']
    calls={'writer':0,'review':0}
    class Gateway:
        def chat(self,messages,**kwargs):
            data=json.loads(messages[-1]['content'])
            if 'schema' in data:
                calls['review']+=1
                if calls['review']==1:return '{}'
                response=completion_review(data,kind)
                response['blocking_issues']=['正文中的职责解释不准确，必须修复。']
                return json.dumps(response)
            calls['writer']+=1
            return BODY if kind=='report' else json.dumps(quiz_envelope()['content'])
    gateway=Gateway()
    def run(checkpoint):
        if kind=='report':return generate_reviewed_report(value,gateway,checkpoint=checkpoint)
        return ReviewedResourceGenerator(gateway,checkpoint=checkpoint).generate(value,job_id='j',config_snapshot_id='c')
    with pytest.raises(GenerationFailure) as first:run(port)
    before=port.load_review_candidate()['content_digest']
    adapter.artifacts.fail(child,first.value.detail)
    adapter.artifacts.resume_review(parent,child['artifact_id'],recovery_key='semantic-rejection')
    renewed=adapter.artifacts.claim('alice',child['artifact_id'])
    resumed=adapter.artifacts.checkpoint_port(renewed)
    with pytest.raises(GenerationFailure) as error:run(resumed)
    assert error.value.detail.category=='content' and error.value.detail.retry_scope=='content'
    assert calls=={'writer':1,'review':2}
    assert resumed.load_review_candidate()['content_digest']==before
    # Replay the persisted rejection after a crash between save and raise.
    with pytest.raises(GenerationFailure) as replay:run(resumed)
    assert replay.value.detail.category=='content'
    assert calls=={'writer':1,'review':2}


@pytest.mark.skipif(os.getenv('D_CONTENT_REAL_MODEL')!='1',reason='opt-in real review of the newly observed mixed-claim counterexample')
def test_real_model_rejects_wrong_criticism_of_a_correct_subclaim():
    from pathlib import Path
    import dotenv
    from app.chat.harness.content_gateway import ContentGateway
    evidence_dir=Path(__file__).resolve().parents[4]/'docs/acceptance/artifacts/2026-09-19-preparation-content'
    previous=json.loads((evidence_dir/'native-quiz-first-pass-counterexample.json').read_text())
    content=previous['artifact']['content']
    assert '把计算错给了程序' in content['questions'][0]['explanation']
    settings=dotenv.dotenv_values(os.environ['D_CONTENT_ENV_FILE'])
    gateway=ContentGateway(api_base=settings['DEEPSEEK_BASE_URL'],api_key=settings['DEEPSEEK_API_KEY'],
        model_name=settings.get('LLM_MODEL') or 'deepseek-v4-pro')
    checked,feedback=review_content('quiz',content,{'teaching_context':previous['teaching_context']},gateway)
    option=checked.question_checks[0].option_checks[2]
    assert feedback and not option.explanation_valid
    assert option.independent_correct is False
    if os.getenv('D_CONTENT_EVIDENCE_DIR'):
        Path(os.environ['D_CONTENT_EVIDENCE_DIR'],'real-mixed-claim-review.json').write_text(json.dumps({
            'scope':'real direct-model re-review of exact native false-negative candidate',
            'content':content,'review':checked.model_dump(),'feedback':feedback},ensure_ascii=False,indent=2))
