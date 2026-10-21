from types import SimpleNamespace
import json
import pytest
from app.services import hyperframes_classroom as service
from core.course_storage import CourseStorageManager
from tests.hyperframes.test_context_serving import lesson
from tests.hyperframes.native_workflow_fixtures import Runner, Runtime, Gateway
from app.integrations.hyperframes.generation import generate_content
from app.integrations.hyperframes.projects import ProjectStore


@pytest.mark.parametrize('metadata,visibility', [({},'private'),({'origin_type':'standard'},'course'),({'harness_config':{'id':'h'}},'private')])
def test_native_job_preserves_visibility_sources_and_pdf(tmp_path, monkeypatch, metadata, visibility):
    monkeypatch.setenv('COURSE_STORAGE_ROOT',str(tmp_path/'courses'))
    manager=CourseStorageManager(root_path=str(tmp_path/'courses'));manager.create_course_structure('c')
    captured={}
    source=SimpleNamespace(context_text='原始证据',mode='selected_documents',documents=(),to_snapshot=lambda:{'mode':'selected_documents'})
    context=SimpleNamespace(owner_user_id='alice',course_id='c',task_id='j',progress=lambda *a:None,is_cancel_requested=lambda:False)
    async def research(**kwargs): return '原始证据'
    monkeypatch.setattr(service,'_build_research_context',research)
    monkeypatch.setattr('app.self_learning.service.gateway',lambda owner:object())
    monkeypatch.setattr(service,'update_job',lambda *a,**k:captured.update(job=k))
    def generate(payload,**kwargs):
        captured['payload']=vars(payload)
        return {'content':lesson(),'generation_state':{}}
    monkeypatch.setattr(service,'generate_classroom',generate)
    service.generate_and_persist({'course_id':'c','pdf_content':{'pages':['PDF正文']},'material_metadata':metadata},context,manager,source,'讲解')
    saved=manager.get_generated_material('c','classroom','classroom_j',owner_user_id='alice')
    assert saved['visibility']==visibility
    assert captured['payload']['pdf_content']=={'pages':['PDF正文']}
    assert captured['payload']['research_context']=='原始证据'
    assert saved['source_snapshot']['mode']=='selected_documents'
    assert captured['job']['result_ref']['version']==saved['version']


def test_local_media_is_preserved_in_project_and_archive(tmp_path):
    import zipfile
    audio=tmp_path/'voice.mp3';audio.write_bytes(b'voice')
    store=ProjectStore(tmp_path/'projects')
    gateway=Gateway()
    content=generate_content(SimpleNamespace(title='媒体课堂',focus='讲解',classroom_options={}),
        gateway=gateway,artifact={'resource_id':'media'},runtime=Runtime(),store=store,
        runner_factory=Runner,narrate=lambda *a:audio,media_files={'assets/media/photo.png':b'photo'})
    assert store.file(content['project'],'assets/media/photo.png').read_bytes()==b'photo'
    with zipfile.ZipFile(store.file(content['project'],'exports/project.zip')) as archive:
        assert archive.read('assets/media/photo.png')==b'photo'


def test_asset_packaging_never_reads_arbitrary_local_or_remote_paths(tmp_path,monkeypatch):
    from app.integrations.hyperframes.assets import selected_media
    path=tmp_path/'a.png';path.write_bytes(b'image')
    monkeypatch.setattr('app.api.searched_images._resolve_safe_path',lambda name:path if name=='a.png' else None)
    files,snapshot=selected_media({'selected':[
        {'local_url':'/api/images/searched/a.png','slot_id':'valid'},
        {'local_url':'file:///etc/passwd','slot_id':'host'},
        {'local_url':'https://example.com/a.png','slot_id':'remote'}]},owner='alice')
    assert len(files)==1 and next(iter(files.values()))==b'image'
    assert len(snapshot['selected'])==1 and len(snapshot['packaging_rejected'])==2


def test_revision_preserves_authored_assets_and_uses_cancel_context(tmp_path,monkeypatch):
    from app.artifact_revision.hyperframes import regenerate
    store=ProjectStore(tmp_path/'projects')
    project=store.publish('hf_revision',{'index.html':'<img src="assets/diagram.svg">',
        'assets/diagram.svg':'<svg/>','assets/custom.js':'window.custom=1',
        'assets/gsap.min.js':'bundled','assets/media/photo.png':b'photo',
        'tools/animate.mjs':'export const native=1','public/reference.png':b'original image'})
    content=lesson(project);captured={}
    monkeypatch.setattr('app.integrations.hyperframes.projects.ProjectStore',lambda:store)
    def generate(payload,**kwargs):
        captured.update(payload=payload,kwargs=kwargs)
        return {'content':content}
    monkeypatch.setattr('app.integrations.hyperframes.generation.generate_classroom',generate)
    service=SimpleNamespace(is_cancel_requested=lambda:False)
    assert regenerate(service,content,content,'调整说明')==content
    assert captured['payload'].original_files['assets/diagram.svg']=='<svg/>'
    assert captured['payload'].original_files['assets/custom.js']=='window.custom=1'
    assert 'assets/gsap.min.js' not in captured['payload'].original_files
    assert captured['kwargs']['media_files']['assets/media/photo.png']==b'photo'
    assert captured['payload'].original_files['tools/animate.mjs']=='export const native=1'
    assert captured['kwargs']['media_files']['public/reference.png']==b'original image'
    assert captured['kwargs']['context'] is service
