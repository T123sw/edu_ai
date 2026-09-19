from dataclasses import replace
import json
from types import SimpleNamespace
import httpx
import pytest
from app.course_preparation.source_snapshots import SourceSnapshots, SnapshotScope
from app.course_preparation.research_agent import ResearchAgent, ResearchError
from app.course_preparation.research_contracts import Candidate, FetchArgs, ResearchState
from app.course_preparation.adapters.sources import PolicySources
from app.course_preparation.schemas import PreparationRequest
from uuid import uuid4


def scope(**kw):
    return SnapshotScope(**{'owner':'alice','preparation':'task','source_policy':'open',
                           'config_version':'v1','guard':lambda:None,**kw})


def test_paginate_restart_and_short_tail_are_same_immutable_snapshot(tmp_path):
    content='First page content. '*260+'Second page content. '*260+'last 13 chars'
    calls=[]; checkpoint={}; file=tmp_path/'checkpoint.json'
    def read(url,**kw): calls.append(url); return content
    request=PreparationRequest(request_id=uuid4(),operation='create_course',goal='Read source')
    candidate=Candidate(candidate_id='src',url='https://example.edu/a',title='A',snippet='not evidence')
    state=ResearchState(candidates=(candidate,))
    for offset in (0,5000,10000):
        snapshots=SourceSnapshots(checkpoint,persist=lambda:file.write_text(json.dumps(checkpoint)))
        sources=PolicySources(owner='alice',request=request,documents=None,web=SimpleNamespace(read=read),snapshots=snapshots,scope=scope())
        agent=ResearchAgent(model=None,sources=sources)
        state=agent._execute('fetch_source',FetchArgs(candidate_id='src',offset_chars=offset),request,state,timeout=20,reserve=None)
        checkpoint=json.loads(file.read_text())  # simulate process restart, not in-memory cache
    assert calls==[candidate.url]
    assert len({e.snapshot_id for e in state.evidence})==1
    assert len({e.snapshot_sha256 for e in state.evidence})==1
    assert ''.join(e.content for e in state.evidence)==content


def test_redirect_alias_and_config_owner_task_isolation():
    calls=[]; cache=SourceSnapshots()
    def read(url,**kw): calls.append(url); return {'canonical_url':'https://example.edu/new','content':'body '*50}
    first=cache.get_or_fetch('https://example.edu/old#fragment',read=read,scope=scope(),timeout=1)
    assert cache.get_or_fetch('https://example.edu/new',read=read,scope=scope(),timeout=1)==first
    for change in ({'owner':'bob'},{'config_version':'v2'},{'preparation':'other'}):
        assert cache.get_or_fetch('https://example.edu/new',read=read,scope=scope(**change),timeout=1).snapshot_id!=first.snapshot_id
    assert len(calls)==4


def test_cache_hit_rechecks_policy_guard_and_expiry_without_replacing_body():
    cache=SourceSnapshots(); calls=[]
    def read(*a,**kw): calls.append(1); return 'original '*30
    first=cache.get_or_fetch('https://example.edu/a',read=read,scope=scope(),timeout=1)
    def deny(): raise PermissionError('canceled')
    for active in (scope(guard=deny),scope(source_policy='uploaded_only'),scope(expires_at='2000-01-01T00:00:00+00:00')):
        with pytest.raises((PermissionError,ResearchError)):
            cache.get_or_fetch('https://example.edu/a',read=read,scope=active,timeout=1)
    assert cache.get_or_fetch('https://example.edu/a',read=lambda *a,**kw:'changed '*50,scope=scope(),timeout=1)==first
    assert len(calls)==1


def test_failure_and_corrupt_cache_never_become_evidence():
    cache=SourceSnapshots()
    with pytest.raises(ResearchError,match='EXTRACT_NO_BODY'):
        cache.get_or_fetch('https://example.edu/a',read=lambda *a,**kw:'',scope=scope(),timeout=1)
    assert not cache.records
    cache.get_or_fetch('https://example.edu/a',read=lambda *a,**kw:'body '*30,scope=scope(),timeout=1)
    next(iter(cache.records.values()))['content']='corrupted'
    with pytest.raises(ResearchError,match='SNAPSHOT_CORRUPT'):
        cache.get_or_fetch('https://example.edu/a',read=lambda *a,**kw:None,scope=scope(),timeout=1)


def test_fallback_counts_each_attempt_and_reports_capabilities(monkeypatch):
    from app.course_preparation import research_sources as module
    calls=[]
    def temporary(*a,**kw):
        raise httpx.HTTPStatusError('503',request=httpx.Request('GET','https://example.edu'),response=httpx.Response(503))
    monkeypatch.setattr(module,'search_tavily',temporary)
    monkeypatch.setattr(module,'search_bocha',lambda *a,**kw:[SimpleNamespace(url='https://example.edu',title='x',content='snippet')])
    source=module.ResearchSources(tavily_key='test',bocha_key='test')
    def attempt(kind,payload,call): calls.append(payload['provider']); return call()
    source.attempt=attempt
    assert source.search('query',limit=1,timeout=2)
    assert calls==['tavily_search','bocha_search']
    assert source.capabilities()['search'][0]['health']=='server'
    assert source.capabilities()['search'][1]['health']=='healthy'
    assert not module.ResearchSources(tavily_key='',bocha_key='test').capabilities()['extract'][0]['configured']


@pytest.mark.parametrize('status,category,retry',[(429,'rate_limit',True),(503,'server',True),(401,'authentication',False),(403,'permission',False)])
def test_provider_error_categories(status,category,retry):
    from app.course_preparation.source_errors import provider_error
    from app.course_preparation.research_agent import RecoverableSourceError
    error=provider_error(httpx.HTTPStatusError('secret',request=httpx.Request('GET','https://example.edu'),response=httpx.Response(status)),'EXTRACT')
    assert error.category==category
    assert isinstance(error,RecoverableSourceError)==retry
    assert 'secret' not in str(error)


def test_production_factory_sql_resume_keeps_snapshot_and_meters_only_external_io(runtime_engine,monkeypatch):
    from sqlalchemy.orm import Session
    from app.database.models import PreparationExecution
    from app.course_preparation import research_factory as module
    from tests.course_preparation.test_runtime_foundation import repo,request
    from app.course_preparation.research_sources import ResearchSources
    from app.course_preparation import research_sources
    calls=[]
    content='actual immutable webpage '*450
    def extract(*a,**kw): calls.append(1); return [SimpleNamespace(url='https://example.edu/page',status='success',content=content)]
    monkeypatch.setattr(research_sources,'extract_tavily',extract)
    monkeypatch.setattr(module,'legacy_factory',lambda *a:ResearchAgent(model=SimpleNamespace(),sources=ResearchSources(tavily_key='fixture')))
    repository=repo(runtime_engine);req=request();task=repository.submit('alice',req)
    context=repository.claim('worker',preparation_id=task['preparation_id'])
    factory=module.research_factory(repository,None,SimpleNamespace(subject=lambda owner:owner))
    checkpoint={'config_snapshot':{'revision':1}}
    for offset in (0,5000,10000):
        agent=factory(context,req,checkpoint)
        state=ResearchState.model_validate(checkpoint.get('research_state',{}))
        if not state.candidates:state=state.model_copy(update={'candidates':(Candidate(candidate_id='src',url='https://example.edu/page',title='page',snippet='snippet'),)})
        def reserve(value):
            checkpoint['research_state']=value.model_dump(mode='json');repository.checkpoint(context,checkpoint)
        state=agent._execute('fetch_source',FetchArgs(candidate_id='src',offset_chars=offset),req,state,timeout=10,reserve=reserve)
        reserve(state)
        with Session(runtime_engine) as session:
            checkpoint=json.loads(json.dumps(session.get(PreparationExecution,(context.preparation_id,1)).checkpoint))
    assert calls==[1]
    assert ''.join(e.content for e in state.evidence)==content
    assert len({e.snapshot_id for e in state.evidence})==1
    assert repository.get_public('alice',context.preparation_id)['budget']['consumed']['calls']==1
    repository.cancel('alice',context.preparation_id)
    with pytest.raises(Exception):
        factory(context,req,checkpoint).sources.read('https://example.edu/page',timeout=10)
    assert calls==[1]


def test_old_evidence_is_preserved_on_changed_page_after_config_revision():
    request=PreparationRequest(request_id=uuid4(),operation='create_course',goal='Read source')
    candidate=Candidate(candidate_id='src',url='https://example.edu/a',title='A',snippet='not evidence')
    cache=SourceSnapshots()
    def agent(version,body):
        return ResearchAgent(model=None,sources=PolicySources(owner='alice',request=request,documents=None,
            web=SimpleNamespace(read=lambda *a,**kw:body),snapshots=cache,scope=scope(config_version=version)))
    first=agent('v1','original '*1400)._execute('fetch_source',FetchArgs(candidate_id='src'),request,
        ResearchState(candidates=(candidate,)),timeout=1,reserve=None)
    with pytest.raises(ResearchError,match='SOURCE_VERSION_CONFLICT'):
        agent('v2','changed '*1400)._execute('fetch_source',FetchArgs(candidate_id='src',offset_chars=5000),
            request,first,timeout=1,reserve=None)
    assert first.evidence[0].content.startswith('original')
