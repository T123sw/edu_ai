from contextvars import ContextVar
from pathlib import Path
import subprocess
import tempfile
import threading
import httpx
from app.integrations.hyperframes.workflow_audio import audio_provider


def test_native_video_lines_overlap_keep_context_and_return_in_script_order():
    selected=ContextVar('selected-provider');selected.set('owner-provider')
    barrier=threading.Barrier(4)
    calls=[]
    with tempfile.TemporaryDirectory(prefix='hf-audio-') as folder:
        root=Path(folder);project=root/'video';project.mkdir()
        fixture=root/'tone.mp3'
        subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','sine=frequency=440:duration=0.1',str(fixture)],check=True)
        def narrate(text,cache,options):
            assert selected.get()=='owner-provider'
            calls.append(text)
            barrier.wait(timeout=3)
            return fixture
        lines=[{'id':str(i),'text':str(i)+'完整场景讲稿。'*10} for i in range(4)]
        with audio_provider(root,guard=lambda:None,options={'voice':'vivian'},narrate=narrate) as socket:
            with httpx.Client(transport=httpx.HTTPTransport(uds=str(socket)),base_url='http://local') as client:
                response=client.post('/audio',json={'project':str(project),'only':'tts','request':{'lines':lines}})
        assert response.status_code==200,response.text
        assert sorted(calls)==sorted(line['text'] for line in lines)
        voices=response.json()['voices']
        assert [v['id'] for v in voices]==['0','1','2','3']
        assert all((project/v['path']).is_file() and v['duration_s']>0 for v in voices)


def test_duplicate_concurrent_lines_share_one_synthesis(tmp_path):
    import time
    project=tmp_path/'video';project.mkdir()
    fixture=tmp_path/'tone.mp3'
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','sine=frequency=440:duration=0.1',str(fixture)],check=True)
    calls=[]
    def narrate(text,cache,options):
        calls.append(text);time.sleep(.2);return fixture
    with audio_provider(tmp_path,guard=lambda:None,options={},narrate=narrate) as socket:
        with httpx.Client(transport=httpx.HTTPTransport(uds=str(socket)),base_url='http://local') as client:
            response=client.post('/audio',json={'project':str(project),'only':'tts','request':{
                'lines':[{'id':str(i),'text':'完全相同的讲稿。'} for i in range(4)]}})
    assert response.status_code==200,response.text
    assert calls==['完全相同的讲稿。']
    assert [v['id'] for v in response.json()['voices']]==['0','1','2','3']
