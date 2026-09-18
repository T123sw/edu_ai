from uuid import uuid4
import pytest
from app.course_preparation.schemas import PreparationRequest
from app.course_preparation.adapters.sources import PolicySources
from app.course_preparation.research_agent import ResearchAgent
from app.course_preparation.research_contracts import ResearchState


def request(mode):
    return PreparationRequest(request_id=uuid4(),operation='create_course',goal='学习 Agent 面试',
        uploads=[{'document_id':'doc','version':1}],source_policy={'mode':mode})


def test_uploaded_only_unmounts_network_and_rejects_direct_calls():
    class Web:
        def search(self,*a,**kw): pytest.fail('network called')
        def read(self,*a,**kw): pytest.fail('network called')
    sources=PolicySources(owner='alice',request=request('uploaded_only'),documents=None,web=Web())
    agent=ResearchAgent(model=None,sources=sources,source_policy='uploaded_only')
    assert 'search_sources' not in [x['function']['name'] for x in agent.tools('research',ResearchState(phase='research'))]
    with pytest.raises(PermissionError): sources.search('agent',limit=5,timeout=1)
    with pytest.raises(PermissionError): sources.read('https://example.com',timeout=1)
    with pytest.raises(PermissionError): sources.read('upload://other/1',timeout=1)


def test_upload_read_rechecks_authorization_and_reports_core_defects():
    from app.course_preparation.adapters.documents import DocumentUnreadable
    class Docs:
        calls=0
        denied=False
        def parse(self,owner,ref):
            self.calls+=1
            if self.denied: raise PermissionError('revoked')
            return {'content':'real text','defects':['PARTIAL_PARSE']}
    docs=Docs(); sources=PolicySources(owner='alice',request=request('uploads_preferred'),documents=docs,web=None)
    with pytest.raises(DocumentUnreadable): sources.read('upload://doc/1',timeout=1)
    docs.denied=True
    with pytest.raises(PermissionError): sources.read('upload://doc/1',timeout=1)
    assert docs.calls==2
