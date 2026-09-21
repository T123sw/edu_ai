"""Configured research assembly. Secrets remain in provider configuration only."""
import os
from .research_dependencies import agent_factory as legacy_factory
from .adapters.sources import PolicySources
from .budget_meter import PreparationModelMeter
from .runtime_contracts import BudgetCost


class MeteredSources:
    def __init__(self,repository,context,sources):
        self.repository,self.context,self.sources=repository,context,sources

    def _call(self,kind,payload,call):
        from uuid import uuid4
        action=self.repository.begin_action(self.context,'source:'+uuid4().hex,kind,payload,BudgetCost(calls=1))
        try: result=call()
        except Exception:
            self.repository.finish_action(self.context,action['action_id'],{'status':'failed'},failed=True)
            raise
        self.repository.finish_action(self.context,action['action_id'],{'status':'read','kind':kind})
        return result

    def search(self,query,**kwargs):
        return self._call('search',{'query':query},lambda:self.sources.search(query,**kwargs))

    def read(self,url,**kwargs):
        return self._call('source_read',{'url':url},lambda:self.sources.read(url,**kwargs))


def research_factory(repository,documents,memory):
    def build(context,request,checkpoint):
        from .intake import effective_request
        request = effective_request(request, checkpoint)
        username=memory.subject(context.owner_user_id)
        agent=legacy_factory(username,checkpoint['config_snapshot'])
        agent.model.meter=PreparationModelMeter(repository,context,
            micro_usd_per_token_upper_bound=int(os.getenv('PREPARATION_MODEL_MICRO_USD_PER_TOKEN_CEILING','10')))
        agent.max_calls=60
        agent.upload_read_limit=max(8, 2*len(request.uploads))
        agent.incremental_findings=True
        agent.source_policy=request.source_policy.mode
        agent.extra_context={'preferences':checkpoint.get('memory_view',{}), 'existing_target':checkpoint.get('target_snapshot'),
            'input_documents':checkpoint.get('input_documents',[]),
            'preference_rule':'本次 request 明确要求优先；偏好仅调整教学表达，不能作为来源或掌握事实'}
        agent.sources=MeteredSources(repository,context,PolicySources(owner=context.owner_user_id,request=request,
            documents=documents,web=agent.sources))
        return agent
    return build
