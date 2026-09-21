import json
import httpx
import pytest
from deepseek_harness import DeepSeekHarness
from app.course_preparation.harness_generation import ContentTools
from tests.course_preparation.test_harness_generation import gateway


def test_structured_submission_preserves_markdown_quotes_and_metadata_without_nested_json():
    expected={'content':'## 原始例子\n程序收到 "name": "add"，路径 C:\\lesson。',
              'objective_bindings':[{'objective_id':'node:o1','locator':{'section_id':'example'},'role':'check'}]}
    observed=[]
    def complete(request):
        payload=json.loads(request.content);observed.append(payload)
        assert all(t['function']['name'] != 'skill' for t in payload['tools'])
        assert '<skill_instructions>' in json.dumps(payload['messages'])
        tool=next(t['function'] for t in payload['tools'] if t['function']['name']!='skill')
        assert tool['name'].endswith('submit_resource_json')
        assert tool['parameters']['properties']['value']['type']=='object'
        return httpx.Response(200,json={'id':'structured','object':'chat.completion','created':1,'model':payload['model'],
            'choices':[{'index':0,'message':{'role':'assistant','content':None,'tool_calls':[
                {'id':'c1','type':'function','function':{'name':tool['name'],'arguments':json.dumps({'value':expected},ensure_ascii=False)}}]},'finish_reason':'tool_calls'}],
            'usage':{'prompt_tokens':50,'completion_tokens':20,'total_tokens':70}})
    model,ledger=gateway(complete,sdk_factory=DeepSeekHarness)
    result=model.for_phase('resource_write',context={'response_format':'json'}).chat([{'role':'user','content':'返回结构化报告'}])
    assert json.loads(result)==expected
    assert len(observed)==len(ledger.actions)==1
    assert ledger.actions[0]['status']=='completed'


def test_structured_tool_rejects_a_string_without_accepting_unparsed_inner_json():
    tools=ContentTools(lambda:None,structured=True)
    assert not tools.call('submit_resource_json',{'value':'{"content": broken}'})['ok']
    assert tools.result is None
    assert tools.fatal.code=='MODEL_RESPONSE_INVALID'


def test_legacy_text_tool_keeps_plain_markdown_compatibility():
    tools=ContentTools(lambda:None)
    assert tools.call('submit_resource_text',{'text':'## Markdown\n"quoted"'})['ok']
    assert tools.result=='## Markdown\n"quoted"'


def test_report_writer_and_independent_reviewer_use_native_object_submissions():
    from tests.course_preparation.test_generated_content_constraints import payload, report_envelope, completion_review
    from app.chat.harness.preparation_content import preparation_metadata
    from app.chat.harness.reviewed_report import generate_reviewed_report, verified_review
    request=payload();envelope=report_envelope();calls=[]
    metadata=preparation_metadata('report',envelope['content'],envelope,request.teaching_context,request.spec_digest)
    review=completion_review({'preparation':metadata})
    review['preparation_checks']=[{'binding_index':i,'passed':c['passed'],'reason':c['reason']}
                                  for i,c in enumerate(review['preparation_checks'])]
    replies=[envelope,review]
    def complete(http_request):
        body=json.loads(http_request.content);calls.append(body)
        name=next(t['function']['name'] for t in body['tools'] if t['function']['name']!='skill')
        assert name.endswith('submit_resource_json')
        if len(calls) == len(replies):
            from jsonschema import Draft202012Validator
            parameters = body['tools'][0]['function']['parameters']
            value_schema = parameters['properties']['value']
            assert 'preparation_checks' in value_schema['required']
            Draft202012Validator.check_schema(parameters)
            validator = Draft202012Validator(parameters)
            validator.validate({'value': replies[-1]})
            missing = {k: v for k, v in replies[-1].items() if k != 'preparation_checks'}
            assert not validator.is_valid({'value': missing})
        return httpx.Response(200,json={'id':'report','object':'chat.completion','created':1,'model':body['model'],
            'choices':[{'index':0,'message':{'role':'assistant','content':None,'tool_calls':[
                {'id':'c1','type':'function','function':{'name':name,'arguments':json.dumps({'value':replies[len(calls)-1]},ensure_ascii=False)}}]},'finish_reason':'tool_calls'}],
            'usage':{'prompt_tokens':50,'completion_tokens':20,'total_tokens':70}})
    model,ledger=gateway(complete,sdk_factory=DeepSeekHarness,context={'artifact_id':'report','spec_digest':request.spec_digest})
    body,state=generate_reviewed_report(request,model)
    assert body==envelope['content'] and verified_review({'content':body,'generation_state':state})
    assert len(calls)==len(ledger.actions)==2
    assert {row['receipt']['model_response']['phase'] for row in ledger.actions}=={'resource_write','resource_review'}


@pytest.mark.parametrize('malformed_first', [False, True])
def test_native_quiz_review_selects_original_explanation_spans_and_persists_canonical_audit(malformed_first):
    from tests.course_preparation.test_generated_content_constraints import payload, quiz_envelope, completion_review
    from app.chat.harness.preparation_content import preparation_metadata
    from app.chat.harness.reviewed_resource import ReviewedResourceGenerator, verified_resource
    request=payload('quiz');envelope=quiz_envelope();calls=[]
    metadata=preparation_metadata('quiz',envelope['content'],envelope,request.teaching_context,request.spec_digest)
    review=completion_review({'preparation':metadata},'quiz')
    review['preparation_checks']=[{'binding_index':i,'passed':c['passed'],'reason':c['reason']}
                                  for i,c in enumerate(review['preparation_checks'])]
    for index,option in enumerate(review['question_checks'][0]['option_checks']):
        option.pop('explanation_excerpt')
        option['explanation_span']={'start_segment':index,'end_segment':index}
    replies=([{'title':'bad wrapper','questions':[]}] if malformed_first else [])+[envelope,review]
    def complete(http_request):
        body=json.loads(http_request.content);calls.append(body)
        name=body['tools'][0]['function']['name']
        assert name.endswith('submit_resource_json')
        if len(calls) == len(replies):
            from jsonschema import Draft202012Validator
            parameters = body['tools'][0]['function']['parameters']
            value_schema = parameters['properties']['value']
            assert 'preparation_checks' in value_schema['required']
            Draft202012Validator.check_schema(parameters)
            validator = Draft202012Validator(parameters)
            validator.validate({'value': replies[-1]})
            missing = {k: v for k, v in replies[-1].items() if k != 'preparation_checks'}
            assert not validator.is_valid({'value': missing})
        return httpx.Response(200,json={'id':'quiz','object':'chat.completion','created':1,'model':body['model'],
            'choices':[{'index':0,'message':{'role':'assistant','content':None,'tool_calls':[
                {'id':'c1','type':'function','function':{'name':name,'arguments':json.dumps({'value':replies[len(calls)-1]},ensure_ascii=False)}}]},'finish_reason':'tool_calls'}],
            'usage':{'prompt_tokens':50,'completion_tokens':20,'total_tokens':70}})
    model,ledger=gateway(complete,sdk_factory=DeepSeekHarness,context={'artifact_id':'quiz','spec_digest':request.spec_digest})
    artifact=ReviewedResourceGenerator(model).generate(request,job_id='j',config_snapshot_id='c')['artifacts'][0]
    assert artifact['content']==envelope['content'] and verified_resource(artifact,'quiz')
    checks=artifact['generation_state']['resource_review']['question_checks'][0]['option_checks']
    assert checks[0]['explanation_excerpt']=='A 正确，程序执行。'
    assert checks[1]['explanation_excerpt']=='B 错误，模型只提出调用。'
    assert len(calls)==len(ledger.actions)==(3 if malformed_first else 2)


def test_review_schema_references_remain_valid_and_are_isolated_per_session():
    from copy import deepcopy
    from jsonschema import Draft202012Validator
    from app.chat.harness.reviewed_resource import IndexedQuizTransportReview
    schema = IndexedQuizTransportReview.model_json_schema()
    original = deepcopy(schema)
    tools = ContentTools(lambda: None, structured=True, response_schema=schema)
    parameters = tools.schemas()[0]['inputSchema']
    Draft202012Validator.check_schema(parameters)
    assert schema == original
    assert parameters['$defs'] == original['$defs']
    assert 'preparation_checks' in parameters['properties']['value']['required']
    assert 'question_checks' in parameters['properties']['value']['required']
    assert parameters['$defs']['IndexedQuestionReview']['additionalProperties'] is False
    parameters['$defs'].clear()
    assert schema == original
    generic = ContentTools(lambda: None, structured=True).schemas()[0]['inputSchema']
    assert '$defs' not in generic
    assert generic['properties']['value']['additionalProperties'] is True


@pytest.mark.parametrize('always_invalid', [False, True])
def test_native_review_schema_errors_are_corrected_before_dispatch_with_bounded_metering(monkeypatch, always_invalid):
    from copy import deepcopy
    from app.course_preparation.harness_provider import CompletionFormatError
    schema = {'type': 'object', 'additionalProperties': False,
              'required': ['preparation_checks', 'blocking_issues'],
              'properties': {'preparation_checks': {'type': 'array', 'items': {'type': 'object'}},
                             'blocking_issues': {'type': 'array', 'items': {'type': 'string'}}}}
    expected = {'preparation_checks': [], 'blocking_issues': ['实际推演存在错误，不能通过']}
    calls, dispatched = [], []
    original = ContentTools.call
    def submit(self, name, arguments):
        dispatched.append(deepcopy(arguments))
        return original(self, name, arguments)
    monkeypatch.setattr(ContentTools, 'call', submit)
    def complete(request):
        payload = json.loads(request.content);calls.append(payload)
        value = deepcopy(expected)
        if always_invalid or len(calls) == 1:
            value.pop('preparation_checks')
        elif len(calls) == 2:
            value['explanation_valid_note'] = '不属于 schema'
        if len(calls) > 1:
            assert 'schema' in payload['messages'][-1]['content']
            assert '未执行' in payload['messages'][-1]['content']
        name = payload['tools'][0]['function']['name']
        return httpx.Response(200, json={'id': 'schema', 'object': 'chat.completion', 'created': 1,
            'model': payload['model'], 'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': None,
            'tool_calls': [{'id': 'c1', 'type': 'function', 'function': {'name': name,
            'arguments': json.dumps({'value': value}, ensure_ascii=False)}}]}, 'finish_reason': 'tool_calls'}],
            'usage': {'prompt_tokens': 50, 'completion_tokens': 20, 'total_tokens': 70}})
    model, ledger = gateway(complete, sdk_factory=DeepSeekHarness)
    reviewer = model.for_phase('resource_review', context={'response_format': 'json'}).with_response_schema(schema)
    if always_invalid:
        with pytest.raises(CompletionFormatError):reviewer.chat([{'role': 'user', 'content': '独立审查'}])
        assert dispatched == []
    else:
        result = reviewer.chat([{'role': 'user', 'content': '独立审查'}])
        assert json.loads(result) == expected
        assert dispatched == [{'value': expected}]
    assert len(calls) == len(ledger.actions) == 3
    assert all(row['status'] == 'completed' for row in ledger.actions)
