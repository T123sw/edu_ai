"""Metered text completions for existing report/quiz review services."""
import json
import time
from datetime import datetime,timezone
import httpx
from .budget_meter import PreparationModelMeter
from .context import encoded_size
from .research_agent import ResearchError

# Public compatibility location for consumers of the preparation gateway.
from .harness_generation import PreparationHarnessGateway, scoped_gateway


class GenerationGateway:
    def __init__(self,configured,store,context,*,deadline,canceled=lambda:False,client_factory=httpx.Client):
        self.configured,self.store,self.context=configured,store,context
        self.deadline,self.canceled,self.client_factory=deadline,canceled,client_factory
        self.meter=PreparationModelMeter(store,context)

    def chat(self,messages,temperature=.2,max_tokens=12000):
        maximum=encoded_size(messages)+512
        if maximum+max_tokens>128000: raise ResearchError('CONTEXT_BUDGET_EXCEEDED','生成规格超过上下文预算')
        for candidate in self.configured.candidates:
            if self.canceled(): raise ResearchError('CANCELED','生成已取消')
            from .runtime_contracts import remaining_seconds
            remaining = remaining_seconds(self.deadline)
            if remaining<=1: raise ResearchError('BUDGET_EXHAUSTED','父任务总时限耗尽')
            timeout=min(120,remaining)
            action=self.meter.start(input_upper_bound=maximum,output_limit=max_tokens,model=candidate['model_name'])
            extra=self.configured._thinking_params(candidate['model_name'])
            if str(candidate['model_name']).lower().startswith('deepseek-v4'): extra={**extra,'thinking':{'type':'disabled'}}
            payload={'model':candidate['model_name'],'messages':messages,'temperature':temperature,
                     'max_tokens':max_tokens,'stream':False,**extra}
            settled=False
            try:
                deadline=time.monotonic()+timeout
                with self.client_factory(timeout=httpx.Timeout(timeout,connect=min(10,timeout))) as client:
                    with client.stream('POST',candidate['api_base'].rstrip('/')+'/chat/completions',
                            headers=self.configured._build_headers(candidate.get('api_key')),json=payload) as response:
                        response.raise_for_status(); body=bytearray()
                        for chunk in response.iter_bytes():
                            body.extend(chunk)
                            if len(body)>2_000_000 or time.monotonic()>deadline: raise ValueError('MODEL_RESPONSE_LIMIT')
                        data=json.loads(body)
                self.meter.finish(action,usage=data.get('usage'),response_data=data)
                settled=True
                choices=data.get('choices')
                if not isinstance(choices,list) or len(choices)!=1 or choices[0].get('finish_reason')!='stop':
                    raise ValueError('MODEL_RESPONSE_INCOMPLETE')
                text=choices[0].get('message',{}).get('content')
                if not isinstance(text,str) or not text.strip(): raise ValueError('MODEL_RESPONSE_EMPTY')
                return text
            except httpx.HTTPError:
                if not settled: self.meter.finish(action,failed=True)
                continue
            except Exception:
                if not settled: self.meter.finish(action,failed=True)
                raise
        raise ResearchError('PROVIDER_UNAVAILABLE','生成模型服务不可用')
