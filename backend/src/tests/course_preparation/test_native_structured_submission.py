import json
import httpx
from deepseek_harness import DeepSeekHarness
from app.course_preparation.harness_generation import ContentTools
from tests.course_preparation.test_harness_generation import gateway


def test_structured_submission_preserves_markdown_quotes_and_metadata_without_nested_json():
    expected={'content':'## 原始例子\n程序收到 "name": "add"，路径 C:\\lesson。',
              'objective_bindings':[{'objective_id':'node:o1','locator':{'section_id':'example'},'role':'check'}]}
    observed=[]
    def complete(request):
        payload=json.loads(request.content);observed.append(payload)
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
    replies=[envelope,completion_review({'preparation':metadata})]
    def complete(http_request):
        body=json.loads(http_request.content);calls.append(body)
        name=next(t['function']['name'] for t in body['tools'] if t['function']['name']!='skill')
        assert name.endswith('submit_resource_json')
        return httpx.Response(200,json={'id':'report','object':'chat.completion','created':1,'model':body['model'],
            'choices':[{'index':0,'message':{'role':'assistant','content':None,'tool_calls':[
                {'id':'c1','type':'function','function':{'name':name,'arguments':json.dumps({'value':replies[len(calls)-1]},ensure_ascii=False)}}]},'finish_reason':'tool_calls'}],
            'usage':{'prompt_tokens':50,'completion_tokens':20,'total_tokens':70}})
    model,ledger=gateway(complete,sdk_factory=DeepSeekHarness,context={'artifact_id':'report','spec_digest':request.spec_digest})
    body,state=generate_reviewed_report(request,model)
    assert body==envelope['content'] and verified_review({'content':body,'generation_state':state})
    assert len(calls)==len(ledger.actions)==2
    assert {row['receipt']['model_response']['phase'] for row in ledger.actions}=={'resource_write','resource_review'}
