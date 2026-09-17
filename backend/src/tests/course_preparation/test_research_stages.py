from app.course_preparation.lifecycle_repository import LifecycleRepository
from app.course_preparation.research_stages import ResearchStages
from app.course_preparation.runner import PreparationRunner
from app.course_preparation.research_agent import ResearchAgent
from tests.course_preparation.test_research_flow import Model, Sources, request


def test_full_lifecycle_research_survives_engine_reassembly_and_stops_before_generation(runtime_engine):
    class Auth:
        def authorize(self,*args): pass
    repo=LifecycleRepository(runtime_engine,authorizer=Auth())
    sources=Sources()
    task=repo.submit('alice',request())
    for step in range(14):
        # A fresh runner/agent sees only durable checkpoint data on each step.
        stages=ResearchStages(repo,lambda *args:ResearchAgent(model=Model(),sources=sources),None)
        runner=PreparationRunner(repo,stages.handlers())
        public=repo.get_public('alice',task['preparation_id'])
        if public['stage']=='produce': break
        result=runner.run_step(task['preparation_id'],worker_id=f'worker{step}')
        assert not result.get('failed'), result
    assert public['stage']=='produce'
    assert public['status']=='running'
    assert public['result_ref'] is None
    assert len(sources.searches)==len(sources.reads)==1


def test_uploaded_only_path_does_not_search_and_node_review_is_separate(runtime_engine):
    from app.course_preparation.schemas import PreparationRequest
    from app.course_preparation.adapters.sources import PolicySources
    from app.course_preparation.node_research import NodeEvidenceDecision
    class Auth:
        def authorize(self,*args): pass
    class Documents:
        def parse(self,*args):
            return {'content':Sources().read('upload',timeout=1),'source_hash':'real-hash','parser':'fixture','defects':[]}
        def authorize(self,*args): return {'filename':'lecture.md'}
    class NoWeb:
        def search(self,*args,**kwargs): raise AssertionError('network forbidden')
    repo=LifecycleRepository(runtime_engine,authorizer=Auth()); docs=Documents()
    req=PreparationRequest(**{**request().model_dump(mode='json'),'uploads':[{'document_id':'doc','version':1}], 'source_policy':{'mode':'uploaded_only'}})
    task=repo.submit('alice',req); reviewed=[]
    def factory(context,request,checkpoint):
        return ResearchAgent(model=Model(),sources=PolicySources(owner='alice',request=request,documents=docs,web=NoWeb()),source_policy='uploaded_only')
    def node_reviewer(context,checkpoint,state,node):
        reviewed.append(node.node_key)
        return NodeEvidenceDecision(node_key=node.node_key,sufficient=True,reason='已有终止条件和递减参数的正文依据',source_ids=node.source_ids)
    for step in range(14):
        public=repo.get_public('alice',task['preparation_id'])
        if public['stage']=='produce': break
        stages=ResearchStages(repo,factory,docs,node_reviewer=node_reviewer)
        result=PreparationRunner(repo,stages.handlers()).run_step(task['preparation_id'],worker_id=str(step))
        assert not result.get('failed'), result
    assert public['stage']=='produce'
    assert reviewed==['n1']
