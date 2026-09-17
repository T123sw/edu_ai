"""Bounded child fan-out; waiting releases the parent worker slot."""
from .generation_contracts import ResourceSpec
from .runtime_contracts import BudgetCost
from .tool_registry import digest
from .runner import StepResult
from .research_agent import ResearchError


class ProductionStages:
    def __init__(self,repository,generation,memory,*,concurrency=2):
        self.repository,self.generation,self.memory=repository,generation,memory
        self.concurrency=max(1,min(concurrency,4))

    def produce(self,context):
        checkpoint=dict(context.checkpoint)
        self.memory.validate(context,checkpoint)
        request=self.repository.get(owner_user_id=context.owner_user_id,preparation_id=context.preparation_id).request
        specifications=checkpoint.get('resource_specs')
        if specifications is None:
            kinds=list(dict.fromkeys(['report','quiz',*request.overrides.required_resource_types]))
            if any(k not in ('report','quiz','classroom') for k in kinds):
                raise ResearchError('RESOURCE_TYPE_UNAVAILABLE','当前完整准备链路支持报告、习题和课堂')
            specifications=[]
            for node in checkpoint['plan']['nodes']:
                for kind in kinds:
                    spec=ResourceSpec(node_id=node['node_key'],title=node['title'],resource_type=kind,
                        objectives=node['objectives'],objective_ids=[node['node_key']+':o'+str(i+1) for i in range(len(node['objectives']))],
                        evidence=checkpoint['node_evidence'][node['node_key']],language=checkpoint['brief']['language'],
                        audience=checkpoint['brief']['audience'],minutes=node['minutes'],learning_check=node['self_check'],
                        memory_subject=checkpoint['memory_subject'],memory_refs=checkpoint['memory_refs'],
                        memory_epoch=checkpoint['memory_view']['memory_epoch'],config_snapshot=checkpoint['config_snapshot'])
                    specifications.append(spec.model_dump(mode='json'))
            checkpoint['resource_specs']=specifications
        valid_keys={digest(s) for s in specifications}
        receipts={k:v for k,v in checkpoint.get('generation_receipts',{}).items() if k in valid_keys}
        results={k:v for k,v in checkpoint.get('artifact_results',{}).items() if k in valid_keys}
        active=0
        for key,receipt in receipts.items():
            result=self.generation.read_result(context.owner_user_id,receipt)
            results[key]=result
            if result['status'] in ('pending','running'): active+=1
        for spec in specifications:
            key=digest(spec)
            if key in receipts: continue
            if active>=self.concurrency: break
            action=self.repository.begin_action(context,'generation:'+key,'generate_resource',spec,BudgetCost(calls=1))
            if action['status']=='completed': receipt=action['receipt']
            else:
                receipt=self.generation.reconcile(context,spec,action['action_id']) if action['replay'] else self.generation.submit(context,spec,action['action_id'])
                self.repository.finish_action(context,action['action_id'],receipt)
            receipts[key]=receipt; active+=1
        checkpoint.update(generation_receipts=receipts,artifact_results=results)
        if len(results)==len(specifications) and all(r['status'] in ('draft','failed') for r in results.values()):
            checkpoint['artifacts']=list(results.values())
            return StepResult(checkpoint,'review')
        return StepResult(checkpoint,wait_seconds=2)
