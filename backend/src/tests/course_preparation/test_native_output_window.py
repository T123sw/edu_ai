import json
import httpx
import pytest
from deepseek_harness import DeepSeekHarness
from tests.course_preparation.test_harness_intake import adapter, TOOL
from app.course_preparation.harness_adapter import PreparationTools
from app.course_preparation.context import context_packet, encoded_size


@pytest.mark.parametrize('extra_bytes', [0, 8000])
def test_native_wrapper_shares_window_without_dropping_source_or_raising_ceiling(extra_bytes):
    # Fill the initial packet close to its limit; the native SDK adds tool and
    # Skill framing afterwards. All source bytes must still reach the provider.
    context={'phase':'resource_review','full_content':'x'*1000}
    initial=context_packet(context,[TOOL],max_tokens=128000,output_tokens=32768,native_skill=True)
    context['full_content']='x'*(1000+128000-32768-initial['input_token_upper_bound']-1024+extra_bytes)
    context_packet(context,[TOOL],max_tokens=128000,output_tokens=32768,native_skill=True)
    calls=[]; ledger=[]
    def complete(request):
        body=json.loads(request.content);calls.append(body)
        assert context['full_content'] in json.dumps(body['messages'])
        assert 8192 <= body['max_tokens'] < 32768
        assert encoded_size(body)+512+body['max_tokens'] <= 128000
        name=next(t['function']['name'] for t in body['tools'] if t['function']['name']!='skill')
        return httpx.Response(200,json={'id':'window','object':'chat.completion','created':1,'model':'test',
            'choices':[{'index':0,'message':{'role':'assistant','content':None,'tool_calls':[
                {'id':'c1','type':'function','function':{'name':name,'arguments':'{"summary":"reviewed"}'}}]},'finish_reason':'tool_calls'}],
            'usage':{'prompt_tokens':20000,'completion_tokens':10,'total_tokens':20010}})
    class Meter:
        def start(self,**kwargs):ledger.append(kwargs);return kwargs
        def finish(self,action,**kwargs):pass
    model=adapter(DeepSeekHarness,client_factory=lambda **kw:httpx.Client(transport=httpx.MockTransport(complete),**kw),meter=Meter())
    model.gateway._build_headers=lambda key:{};model.gateway._thinking_params=lambda model:{}
    toolset=PreparationTools([TOOL]);toolset.terminal_on_result=True
    assert model._run(context,[TOOL],timeout=30,toolset=toolset,output_tokens=32768)==('record_input_document',{'summary':'reviewed'})
    assert len(calls)==len(ledger)==1 and ledger[0]['output_limit']==calls[0]['max_tokens']
