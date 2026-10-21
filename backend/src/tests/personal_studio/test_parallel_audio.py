import asyncio
from pathlib import Path
from types import SimpleNamespace
import subprocess
import pytest
from app.services.studio_learning_resources import render_podcast, _Canceled

@pytest.fixture
def anyio_backend(): return 'asyncio'

@pytest.mark.anyio
async def test_chapters_overlap_and_join_in_authored_order(tmp_path, monkeypatch):
    from app.services import classroom_narration
    fixture = tmp_path/'tone.mp3'
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','sine=frequency=440:duration=0.1',str(fixture)],check=True)
    entered=[];done=[];gate=asyncio.Event();progress=[]
    async def speak(*,action,audio_dir):
        i=int(action['text']);entered.append(i)
        if len(entered)==7: gate.set()
        await asyncio.wait_for(gate.wait(),2)
        await asyncio.sleep((6-i)*.01)
        path=audio_dir/f'chapter-{i}.mp3';path.write_bytes(fixture.read_bytes());done.append(i)
        return path
    monkeypatch.setattr(classroom_narration,'narration_audio',speak)
    real=asyncio.create_subprocess_exec
    async def capture(*args,**kwargs):
        if '-concat' in args: raise AssertionError('wrong ffmpeg syntax')
        if 'concat' in args:
            listing=Path(args[args.index('-i')+1]).read_text()
            assert listing == ''.join(f"file '../chapter-{i}.mp3'\n" for i in range(7))
        return await real(*args,**kwargs)
    monkeypatch.setattr(asyncio,'create_subprocess_exec',capture)
    context=SimpleNamespace(is_cancel_requested=lambda:False,is_lease_valid=lambda:True,progress=lambda *p:progress.append(p))
    await render_podcast({'segments':[{'text':str(i)} for i in range(7)]},tmp_path/'audio',context)
    assert entered==list(range(7)) and done!=entered
    assert (tmp_path/'audio/podcast.mp3').is_file() and '7/7' in progress[-1][2]

@pytest.mark.anyio
async def test_cancel_stops_all_chapter_waiters_without_publishing(tmp_path,monkeypatch):
    from app.services import classroom_narration
    started=[];stopped=[]
    async def speak(*,action,audio_dir):
        started.append(action['text'])
        try: await asyncio.sleep(60)
        finally: stopped.append(action['text'])
    monkeypatch.setattr(classroom_narration,'narration_audio',speak)
    context=SimpleNamespace(is_cancel_requested=lambda:len(started)==7,is_lease_valid=lambda:True,progress=lambda *p:None)
    with pytest.raises(_Canceled):
        await asyncio.wait_for(render_podcast({'segments':[{'text':str(i)} for i in range(7)]},tmp_path,context),2)
    assert len(stopped)==7 and not (tmp_path/'podcast.mp3').exists()
