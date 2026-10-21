import json
from uuid import uuid4
import pytest
from sqlalchemy import create_engine,select
from sqlalchemy.pool import StaticPool
from app.practice.guidance.contracts import make_manifest
from app.practice.guidance.bundle import replay
from app.practice.guidance.repository import GuidedRepository,SessionConflict,SessionNotFound
from app.practice.guidance.db_models import PracticeSession,PracticeEvent,PracticeJournalEntry
from app.practice.guidance.verify import verify

@pytest.fixture
def repository():
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    PracticeSession.__table__.create(engine);PracticeEvent.__table__.create(engine);PracticeJournalEntry.__table__.create(engine)
    yield GuidedRepository(engine)
    engine.dispose()

def test_owner_isolation_and_idempotent_open(repository):
    m=make_manifest('quicksort');a=repository.open('a','lab',m)
    assert repository.open('a','lab',m)==a
    with pytest.raises(SessionNotFound):repository.get('b','lab',a['session_id'])

def test_duplicate_batches_are_receipts_not_repeated_actions(repository):
    m=make_manifest('quicksort');s=repository.open('a','lab',m)
    batch={'batch_id':'batch','revision':m['revision'],'expected_seq':0,'commands':[{'id':'event','type':'action','action':'select','value':0}]}
    result=repository.append('a','lab',s['session_id'],m,batch)
    assert result['saved_seq']==1
    assert repository.append('a','lab',s['session_id'],m,batch)==result
    with pytest.raises(SessionConflict):repository.append('a','lab',s['session_id'],m,{**batch,'batch_id':'new'})
    changed=json.loads(json.dumps(batch));changed['commands'][0]['value']=2
    with pytest.raises(SessionConflict):repository.append('a','lab',s['session_id'],m,changed)

def test_conflicting_tab_does_not_overwrite_state(repository):
    m=make_manifest('quicksort');s=repository.open('a','lab',m)
    batch={'batch_id':'one','revision':m['revision'],'expected_seq':0,'commands':[{'id':'event','type':'action','action':'select','value':0}]}
    repository.append('a','lab',s['session_id'],m,batch)
    with pytest.raises(SessionConflict):repository.append('a','lab',s['session_id'],m,{**batch,'batch_id':'two','commands':[{'id':'other','type':'retry'}]})
    assert repository.get('a','lab',s['session_id'])['state']['attempts']['pivot']['model']['selected']==0

def test_server_replays_and_refuses_forged_completion_payload(repository):
    m=make_manifest('quicksort');s=repository.open('a','lab',m)
    batch={'batch_id':'batch','revision':m['revision'],'expected_seq':0,'commands':[{'id':'event','type':'action','action':'complete','value':True}]}
    result=repository.append('a','lab',s['session_id'],m,batch)
    assert result['state']['feedback']['outcome']=='blocked'
    assert not result['state']['attempts']['pivot']['complete']
    assert result['state']['attempts']['pivot']['model']['array']==m['initial']

def test_independent_checker_detects_invalid_sort_and_friction():
    m=make_manifest('quicksort');s=replay(m);s['attempts']['pivot']['model']['array'][0]=99
    with pytest.raises(ValueError):verify(m,s)
    m=make_manifest('friction');s=replay(m);s['attempts']['baseline']['model']['distance']=10
    with pytest.raises(ValueError):verify(m,s)

def test_native_bundle_injected_before_generated_renderer():
    from app.practice.native_runtime import wrap_native_html
    html=wrap_native_html('<html><head></head><body><script>EduGuidance.register({render(){}})</script></body></html>',make_manifest('quicksort'))
    assert html.index('window.__practiceManifest=')<html.index('EduGuidance.register')
    assert 'connect-src' in html

def test_guided_journal_is_scoped_and_free_exploration_is_valid(repository,monkeypatch,tmp_path):
    from app.api import practice as api
    from app.practice.service import PracticeStore
    from app.services.job_store import JobKind,JobStatus
    from types import SimpleNamespace
    store=PracticeStore(root=tmp_path,repository=None)
    monkeypatch.setenv('APP_STATE_PERSISTENCE_MODE','json')
    store.repository=None
    manifest=make_manifest('quicksort')
    artifact={'html':'x','guidance_version':2,'guidance':manifest,'plan':{'steps':[{}, {}, {}]},'science':{}}
    store.put('alice','lab',artifact)
    monkeypatch.setattr(api,'get_job',lambda _:SimpleNamespace(owner_user_id='alice',kind=JobKind.GENERATE_PRACTICE,status=JobStatus.SUCCEEDED))
    monkeypatch.setattr(api,'PracticeStore',lambda:store);monkeypatch.setattr(api,'GuidedRepository',lambda:repository)
    saved=api.open_session('lab',{'username':'alice'})
    response=repository.append('alice','lab',saved['session_id'],manifest,{'batch_id':'explore','revision':manifest['revision'],'expected_seq':0,'commands':[{'id':'enter','type':'enter','step':'explore'}]})
    payload=api.Observation(step=3,session_id=saved['session_id'],step_id='explore',attempt_id='enter',state_revision=1,note='测试')
    assert api.observe('lab',payload,{'username':'alice'})['observations'][0]['step_id']=='explore'

def test_delayed_answer_keeps_original_attempt_and_uses_saved_state(repository,monkeypatch,tmp_path):
    import asyncio
    from app.api import practice as api
    from app.practice.service import PracticeStore
    from app.services.job_store import JobKind,JobStatus
    from types import SimpleNamespace
    monkeypatch.setenv('APP_STATE_PERSISTENCE_MODE','json');store=PracticeStore(root=tmp_path)
    m=make_manifest('quicksort');store.put('alice','lab',{'html':'x','guidance_version':2,'guidance':m,'plan':{'steps':[{}, {}, {}]},'science':{}})
    monkeypatch.setattr(api,'get_job',lambda _:SimpleNamespace(owner_user_id='alice',kind=JobKind.GENERATE_PRACTICE,status=JobStatus.SUCCEEDED))
    monkeypatch.setattr(api,'PracticeStore',lambda:store);monkeypatch.setattr(api,'GuidedRepository',lambda:repository)
    saved=api.open_session('lab',{'username':'alice'})
    async def answer(owner,prompt,**kwargs):
        data=json.loads(prompt);assert data['browser_reported_state']['results']['比较次数']==0
        repository.append('alice','lab',saved['session_id'],m,{'batch_id':'retry','revision':m['revision'],'expected_seq':0,'commands':[{'id':'new-attempt','type':'retry'}]})
        return '先选择基准。'
    monkeypatch.setattr(api,'complete',answer)
    result=asyncio.run(api.ask('lab',api.Question(question='下一步？',state={'results':{'比较次数':999}},step=0,session_id=saved['session_id'],step_id='pivot',attempt_id='initial',state_revision=0),{'username':'alice'}))
    assert result['messages'][-1]['attempt_id']=='initial'
    assert repository.get('alice','lab',saved['session_id'])['state']['attempts']['pivot']['id']=='new-attempt'
