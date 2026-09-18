"""Charge every provider attempt, including fallbacks, to the parent SQL ledger."""
from uuid import uuid4
from .runtime_contracts import BudgetCost


class PreparationModelMeter:
    def __init__(self,repository,context,*,micro_usd_per_token_upper_bound=10):
        self.repository,self.context=repository,context
        self.rate=micro_usd_per_token_upper_bound
        if not isinstance(self.rate,int) or self.rate<1: raise ValueError('MODEL_PRICE_CEILING_REQUIRED')

    def start(self,*,input_upper_bound,output_limit,model):
        maximum=input_upper_bound+output_limit
        return self.repository.begin_action(self.context,'provider:'+uuid4().hex,'model_completion',
            {'model':model,'input_token_upper_bound':input_upper_bound,'output_limit':output_limit,
             'micro_usd_per_token_upper_bound':self.rate},
            BudgetCost(calls=1,tokens=maximum,cost_micro_usd=maximum*self.rate))

    def finish(self,action,*,usage=None,failed=False,response_data=None):
        usage=usage or {}
        # Missing/invalid provider usage retains conservative reservation instead
        # of claiming zero tokens. Monetary amount is an upper-bound estimate.
        count=usage.get('total_tokens')
        reserved=action['reserved']
        valid=isinstance(count,int) and not isinstance(count,bool) and 0<count<=reserved['tokens']
        cost=BudgetCost(calls=1,tokens=count if valid else reserved['tokens'],
            cost_micro_usd=(count*self.rate) if valid else reserved['cost_micro_usd'])
        self.repository.finish_action(self.context,action['action_id'],
            {'usage':{'tokens':cost.tokens,'reported_by_provider':valid},'cost_basis':'configured_upper_bound','model_response':response_data},
            actual=cost,failed=failed)
