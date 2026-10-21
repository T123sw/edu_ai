"""Wire-contract regressions; provider fixtures do not prove model correctness."""
from copy import deepcopy
import json

import httpx
import pytest
from deepseek_harness import DeepSeekHarness
from jsonschema import Draft202012Validator

from app.chat.harness.preparation_write_contract import PreparationWriteContract, bind_write_contract
from app.chat.harness.preparation_content import preparation_metadata
from app.chat.harness.reviewed_resource import ReviewedResourceGenerator, verified_resource
from app.course_preparation.harness_generation import ContentTools
from app.course_preparation.harness_provider import ContentSchemaError, CompletionFormatError
from tests.course_preparation.test_generated_content_constraints import (
    context, payload, quiz_envelope, report_envelope, completion_review,
)
from tests.course_preparation.test_harness_generation import gateway


def envelope():
    value = quiz_envelope()
    value['content']['questions'][0]['difficulty'] = 'easy'
    value['question_time_estimates'] = [
        {'question_id': 'q-tools', 'thinking_seconds': 30, 'reason': '追踪模型提出请求与程序执行两个步骤'}]
    return value


def tools_for(contract):
    return ContentTools(lambda: None, structured=True, response_schema=contract.schema,
                        response_validator=contract.validate_submission)


@pytest.mark.parametrize('kind', ['quiz', 'report'])
def test_write_contract_is_declared_before_submission_and_preserves_values(kind):
    value = envelope() if kind == 'quiz' else report_envelope()
    original = deepcopy(value)
    contract = PreparationWriteContract(kind, context(), 'spec')
    tools = tools_for(contract)
    schema = tools.schemas()[0]['inputSchema']
    Draft202012Validator.check_schema(schema)
    assert schema['additionalProperties'] is False
    assert {'content', 'applied_requirements', 'objective_bindings'} <= set(schema['required'])
    assert 'value' not in schema['properties']
    tools.validate_arguments('submit_resource_json', value)
    assert tools.call('submit_resource_json', value)['ok']
    assert json.loads(tools.result) == original == value


@pytest.mark.parametrize('fault', [
    'native_body', 'string_body', 'wrapper', 'missing_answer', 'missing_options',
    'unknown_type', 'extra_field', 'unknown_objective', 'unknown_requirement',
    'dangling_question', 'duplicate_question', 'missing_estimate', 'duplicate_estimate',
    'bad_estimate', 'unknown_answer', 'duplicate_answer', 'wrong_role',
])
def test_invalid_structure_or_references_never_acknowledged(fault):
    value = envelope()
    q = value['content']['questions'][0]
    if fault == 'native_body': value = value['content']
    elif fault == 'string_body': value['content'] = json.dumps(value['content'])
    elif fault == 'wrapper': value = {'value': value}
    elif fault == 'missing_answer': del q['answer']
    elif fault == 'missing_options': del q['options']
    elif fault == 'unknown_type': q['type'] = 'essay'
    elif fault == 'extra_field': q['answer_is_correct'] = True
    elif fault == 'unknown_objective': value['objective_bindings'][0]['objective_id'] = 'other-node:o1'
    elif fault == 'unknown_requirement': value['applied_requirements'][0]['requirement_id'] = 'invented'
    elif fault == 'dangling_question': value['objective_bindings'][0]['locator']['question_id'] = 'q-missing'
    elif fault == 'duplicate_question': value['content']['questions'].append(deepcopy(q))
    elif fault == 'missing_estimate': del value['question_time_estimates']
    elif fault == 'duplicate_estimate': value['question_time_estimates'] *= 2
    elif fault == 'bad_estimate': value['question_time_estimates'][0]['thinking_seconds'] = True
    elif fault == 'unknown_answer': q['answer'] = 'Z'
    elif fault == 'duplicate_answer': q.update(type='multiple_choice', answer='A,A')
    elif fault == 'wrong_role': value['objective_bindings'][0]['role'] = 'explanation'
    tools = tools_for(PreparationWriteContract('quiz', context(), 'spec'))
    with pytest.raises(ContentSchemaError):
        tools.validate_arguments('submit_resource_json', value)
    assert tools.result is None and tools.fatal is None  # pre-dispatch correction is still possible
    assert not tools.call('submit_resource_json', value)['ok']  # MCP cannot bypass it
    assert tools.result is None


@pytest.mark.parametrize('kind', ['true_false', 'short_answer'])
def test_non_choice_questions_do_not_need_fake_options(kind):
    value = envelope()
    q = value['content']['questions'][0]
    q.update(type=kind, answer='正确' if kind == 'true_false' else '程序执行')
    del q['options']
    tools_for(PreparationWriteContract('quiz', context(), 'spec')).validate_arguments('submit_resource_json', value)


def test_long_question_does_not_hide_missing_field_in_correction_feedback():
    value = envelope()
    value['content']['questions'][0]['stem'] *= 500
    del value['content']['questions'][0]['options']
    tools = tools_for(PreparationWriteContract('quiz', context(), 'spec'))
    with pytest.raises(ContentSchemaError, match="'options' is a required property") as error:
        tools.validate_arguments('submit_resource_json', value)
    assert 'content.questions.0' in str(error.value)


@pytest.mark.parametrize('kind', ['quiz', 'report'])
def test_patch_schema_uses_existing_paths_and_preserves_identity(kind):
    value = envelope() if kind == 'quiz' else report_envelope()
    previous = deepcopy(value['content'])
    contract = PreparationWriteContract(kind, context(), 'spec', previous=previous, patch=True)
    patch = {k: v for k, v in value.items() if k != 'content'}
    before = 'A 正确' if kind == 'quiz' else '用户请求12加30'
    # Report source repeats the example; choose the entire body for an exact match.
    if kind == 'report': before = previous
    patch['edits'] = [{'path': ['questions', 0, 'explanation'] if kind == 'quiz' else [],
                       'before': before, 'after': before + '（核对后）'}]
    tools = tools_for(contract)
    Draft202012Validator.check_schema(contract.schema)
    tools.validate_arguments('submit_resource_json', patch)
    assert value['content'] == previous
    patch['edits'][0]['path'] = ['questions', 0, 'id']
    with pytest.raises(ContentSchemaError): tools.validate_arguments('submit_resource_json', patch)
    patch['edits'][0]['path'] = ['questions', 0, 'explanation'] if kind == 'quiz' else []
    patch['edits'][0]['before'] = '不存在的旧片段'
    with pytest.raises(ContentSchemaError): tools.validate_arguments('submit_resource_json', patch)


def indexed_review(value, request):
    metadata = preparation_metadata('quiz', value['content'], value, request.teaching_context, request.spec_digest)
    review = completion_review({'preparation': metadata}, 'quiz')
    review['preparation_checks'] = [
        {'binding_index': i, 'passed': c['passed'], 'reason': c['reason']}
        for i, c in enumerate(review['preparation_checks'])]
    for index, option in enumerate(review['question_checks'][0]['option_checks']):
        option.pop('explanation_excerpt')
        option['explanation_span'] = {'start_segment': index, 'end_segment': index}
    return review


def response(body, arguments):
    name = body['tools'][0]['function']['name']
    return httpx.Response(200, json={
        'id': 'schema', 'object': 'chat.completion', 'created': 1, 'model': body['model'],
        'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': None, 'tool_calls': [
            {'id': 'c1', 'type': 'function', 'function': {
                'name': name, 'arguments': json.dumps(arguments, ensure_ascii=False)}}]},
            'finish_reason': 'tool_calls'}],
        'usage': {'prompt_tokens': 50, 'completion_tokens': 20, 'total_tokens': 70}})


def test_quiz_protocol_corrections_only_repair_structure_then_finish(monkeypatch):
    request = payload('quiz')
    good = {'content': envelope()['content']}
    invalid = deepcopy(good)
    invalid['content']['questions'][0]['answer'] = 'Z'
    replies = [good['content'], invalid, good]
    requests, dispatched = [], []
    original_call = ContentTools.call
    def submit(self, name, arguments):
        dispatched.append(deepcopy(arguments))
        return original_call(self, name, arguments)
    monkeypatch.setattr(ContentTools, 'call', submit)
    def complete(http_request):
        body = json.loads(http_request.content)
        requests.append(body)
        schema = body['tools'][0]['function']['parameters']
        assert set(schema['properties']) == {'content'}
        assert schema['additionalProperties'] is False
        if len(requests) in (2, 3):
            assert '未执行' in body['messages'][-1]['content']
        return response(body, replies[len(requests) - 1])
    model, ledger = gateway(complete, sdk_factory=DeepSeekHarness,
                            context={'artifact_id': 'quiz', 'spec_digest': request.spec_digest})
    artifact = ReviewedResourceGenerator(model).generate(request, job_id='j', config_snapshot_id='c')['artifacts'][0]
    assert artifact['content'] == good['content']
    assert verified_resource(artifact, 'quiz')
    assert dispatched == [good]
    assert artifact['generation_state']['resource_review']['decision'] == 'skipped'
    assert len(requests) == len(ledger.actions) == 3
    assert {row['receipt']['model_response']['phase'] for row in ledger.actions} == {'resource_write'}


def test_native_invalid_writer_stops_after_two_corrections_without_dispatch(monkeypatch):
    calls, dispatched = [], []
    monkeypatch.setattr(ContentTools, 'call', lambda *args: dispatched.append(args))
    def complete(request):
        body = json.loads(request.content); calls.append(body)
        return response(body, envelope()['content'])
    model, ledger = gateway(complete, sdk_factory=DeepSeekHarness)
    writer = bind_write_contract(model.for_phase('resource_write', context={}), 'quiz', context(), 'spec')
    with pytest.raises(CompletionFormatError):
        writer.chat([{'role': 'user', 'content': '提交习题'}])
    assert len(calls) == len(ledger.actions) == 3
    assert not dispatched


def test_contract_context_and_schema_do_not_leak_between_phase_views():
    model, _ = gateway(lambda _: pytest.fail('no model call'))
    teaching = context()
    first = bind_write_contract(model.for_phase('resource_write', context={}), 'quiz', teaching, 'spec')
    teaching['objective_ids'].append('mutated')
    second = model.for_phase('resource_review', context={})
    assert first._response_validator is not None and second._response_validator is None
    assert 'mutated' not in json.dumps(first._phase_context)
    assert 'response_schema' not in second._phase_context


@pytest.mark.parametrize('allowed', [False, True])
def test_question_deletion_requires_explicit_contract_and_updated_references(allowed):
    value = envelope()
    second = deepcopy(value['content']['questions'][0])
    second['id'] = 'q-second'
    value['content']['questions'].append(second)
    value['question_time_estimates'].append({
        'question_id': 'q-second', 'thinking_seconds': 30, 'reason': '独立追踪第二次工具调用'})
    previous = deepcopy(value['content'])
    patch = {k: deepcopy(v) for k, v in value.items() if k != 'content'}
    patch['edits'] = [{'op': 'delete', 'path': ['questions', 1],
                       'before': second, 'after': None}]
    contract = PreparationWriteContract('quiz', context(), 'spec',
        previous=previous, patch=True, allow_delete=allowed)
    tools = tools_for(contract)
    Draft202012Validator.check_schema(contract.schema)
    # A removed question must disappear from metadata too.
    with pytest.raises(ContentSchemaError):
        tools.validate_arguments('submit_resource_json', patch)
    patch['question_time_estimates'].pop()
    if allowed:
        tools.validate_arguments('submit_resource_json', patch)
        patch['objective_bindings'][0]['locator']['question_id'] = 'q-second'
        with pytest.raises(ContentSchemaError):
            tools.validate_arguments('submit_resource_json', patch)
    else:
        with pytest.raises(ContentSchemaError):
            tools.validate_arguments('submit_resource_json', patch)
    assert previous == value['content']


@pytest.mark.parametrize('fault', ['unanchored', 'dangling', 'changed_identity'])
def test_report_section_contract_is_checked_before_acknowledgement(fault):
    value = report_envelope()
    previous = value['content']
    if fault == 'unanchored':
        value['content'] = '## 没有稳定定位\n报告正文'
    elif fault == 'dangling':
        value['objective_bindings'][0]['locator']['section_id'] = 'missing'
    else:
        value['content'] = value['content'].replace('id="theory"', 'id="new"')
        value['objective_bindings'][0]['locator']['section_id'] = 'new'
    contract = PreparationWriteContract('report', context(), 'spec',
        previous=previous if fault == 'changed_identity' else None)
    with pytest.raises(ContentSchemaError):
        tools_for(contract).validate_arguments('submit_resource_json', value)
