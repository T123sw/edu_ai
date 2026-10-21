import copy
import time
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from app.integrations.hyperframes.projects import ProjectStore
from app.self_learning.hyperframes_context import timeline_context, classroom_timeline_context
from app.self_learning.contracts import ResourceRef


def lesson(project=None):
    def segment(sid,start,end):
        return dict(id=sid,title=sid,start=start,end=end,narration='讲稿'+sid,visual_description='公式'+sid,
            audio_path='assets/a.mp3',objective_ids=['o1'],source_ids=['source1'],
            events=[dict(start=start,end=end-0.5,target='formula',description='高亮')])
    return dict(format='hyperframes/v1',title='课堂',project=project or dict(id='hf_test',digest='a'*64,entry='index.html'),
        timeline=dict(duration=12,segments=[segment('a',0,5),segment('b',7,12)]),exports={})


def test_boundaries_gaps_and_invalid_positions():
    assert timeline_context(lesson(),4)['current_segment']['id']=='a'
    assert timeline_context(lesson(),5)['location_quality']=='timeline_gap'
    assert timeline_context(lesson(),7)['current_segment']['id']=='b'
    assert timeline_context(lesson(),12)['current_segment']['id']=='b'
    assert timeline_context(lesson(),12)['active_visual_events']==[]
    assert timeline_context(lesson(),12)['previous_segment']['id']=='a'
    for value in (-1,13,float('nan'),float('inf')):
        with pytest.raises(HTTPException): timeline_context(lesson(),value)
    with pytest.raises(HTTPException): timeline_context(lesson(),8,'a')


def test_snapshot_consistency():
    value=classroom_timeline_context({'content':lesson()},{'kind':'hyperframes','seconds':8},{'status':'paused','position':{'seconds':8,'segment_id':'b'}})
    assert value['narration_alignment']=='segment_audio_duration'
    assert value['visual_evidence']=='authored_metadata_not_observed_screenshot'
    assert value['current_segment']['narration']=='讲稿b'
    with pytest.raises(HTTPException):
        classroom_timeline_context({'content':lesson()},{'kind':'hyperframes','seconds':8},{'position':{'seconds':4}})
    with pytest.raises(HTTPException):
        classroom_timeline_context({'content':lesson()},{'kind':'classroom','scene_id':'a'})


def test_native_receipt_and_manifest():
    from app.chat.harness.classroom_policy import classroom_structure_receipt
    from app.chat.harness.reviewed_resource import verified_resource
    from app.resource_learning.manifest import build_classroom_learning_manifest
    content=lesson()
    material={'content':content,'generation_state':{'resource_review':classroom_structure_receipt(content)},'course_id':'c','material_id':'m','version':2}
    assert verified_resource(material,'classroom')
    mutated=copy.deepcopy(material);mutated['content']['timeline']['segments'][0]['narration']='篡改'
    assert not verified_resource(mutated,'classroom')
    assert [s.expected_duration_ms for s in build_classroom_learning_manifest(material).scenes]==[5000,5000]


@pytest.fixture
def api(tmp_path):
    from app.api import hyperframes as hf
    store=ProjectStore(tmp_path)
    project=store.publish('hf_test',{'index.html':'<html>hello</html>','assets/a.mp3':b'0123456789'})
    content=lesson(project)
    class Learning:
        allowed=True
        def for_scope(self,owner,course): return self
        def material(self,course,kind,mid,owner):
            if not self.allowed or owner!='alice' or (course,kind,mid)!=('c','classroom','m'): raise HTTPException(404,'denied')
            return {'version':2,'content':content}
    learning=Learning()
    app=FastAPI();app.include_router(hf.router)
    app.dependency_overrides[hf.project_store]=lambda:store
    app.dependency_overrides[hf.ticket_learning]=lambda:learning
    app.dependency_overrides[hf.service]=lambda:learning
    app.dependency_overrides[hf.get_current_user]=lambda:{'username':'alice'}
    return TestClient(app),hf,learning,content


def test_scoped_playback_range_revocation(api):
    client,hf,learning,content=api
    response=client.post('/api/self-learning/courses/c/materials/classroom/m/versions/2/playback')
    assert response.status_code==200,response.text
    url=response.json()['project_url'];page=client.get(url)
    assert page.status_code==200 and 'sandbox allow-scripts' in page.headers['content-security-policy']
    audio=client.get(url.replace('index.html','assets/a.mp3'),headers={'Range':'bytes=2-5'})
    assert audio.status_code==206 and audio.content==b'2345'
    assert client.get(url.replace('index.html','%252e%252e/private')).status_code==404
    learning.allowed=False
    assert client.get(url).status_code==404


def test_expired_wrong_audience_and_digest(api):
    client,hf,learning,content=api
    ref=ResourceRef(course_id='c',material_type='classroom',material_id='m',version=2)
    ticket,_=hf.issue_ticket('alice',ref,content['project'],now=time.time()-hf.TTL-10)
    assert client.get('/api/hyperframes/projects/'+ticket+'/index.html').status_code==401
    login=hf.auth_manager.create_token('alice')
    assert client.get('/api/hyperframes/projects/'+login+'/index.html').status_code==401
    ticket,_=hf.issue_ticket('alice',ref,{**content['project'],'digest':'f'*64})
    assert client.get('/api/hyperframes/projects/'+ticket+'/index.html').status_code==409


def test_proxy_csp_does_not_repeat_capability_or_overflow_headers(api, monkeypatch):
    client,hf,learning,content=api
    monkeypatch.setenv('VITE_API_BASE_URL','/backend')
    from starlette.requests import Request
    request=Request({'type':'http','scheme':'https','server':('school.example',443),
                     'path':'/api/hyperframes/projects/','query_string':b'',
                     'headers':[], 'root_path':''})
    ticket='long-sensitive-ticket-'*80
    csp=hf.project_csp(request,ticket)
    assert ticket not in csp and len(csp.encode())<2048
    assert 'https://school.example/backend/api/hyperframes/projects/' in csp
    assert 'sandbox allow-scripts' in csp and "default-src 'none'" in csp
    assert 'allow-same-origin' not in csp


def test_publication_preserves_native_project_and_timeline(tmp_path):
    from app.services.material_publication_service import MaterialPublicationService
    from core.course_storage import CourseStorageManager
    manager = CourseStorageManager(root_path=str(tmp_path))
    manager.create_course_structure('c')
    original = lesson()
    assert manager.save_generated_material('c', 'classroom', 'native',
        {**original, 'content': original, 'private_notes': 'SECRET'}, owner_user_id='alice')
    result = MaterialPublicationService(manager).publish(course_id='c', material_type='classroom',
        material_id='native', owner_user_id='alice')
    for key in ('format','project','timeline','exports'):
        assert result.material[key] == original[key]
        assert result.material['content'][key] == original[key]
    assert 'SECRET' not in str(result.material)
