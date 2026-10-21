from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar
import json
from pathlib import Path
import threading
import time
import urllib.request

import pytest

from app.integrations.hyperframes.workflow_agent import WorkflowTools
from app.integrations.hyperframes.workflow_workers import WorkflowWorkers
from tests.hyperframes.test_workflow_host import finish


def settled(pool, count):
    deadline = time.monotonic()+10
    while time.monotonic() < deadline:
        rows = pool.poll(wait_seconds=.05)
        if len(rows) == count and all(r['status'] not in ('queued', 'running') for r in rows):
            return rows
    raise AssertionError(pool.poll())


def test_workers_overlap_batch_queue_context_and_deduplicate(tmp_path):
    gate = threading.Event()
    ready = threading.Barrier(4)
    lock = threading.Lock()
    active, maximum = [0], [0]
    identity = ContextVar('identity');identity.set('owner-config')
    def runner(prompt, **kw):
        assert identity.get() == 'owner-config'
        with lock:
            active[0] += 1;maximum[0] = max(maximum[0],active[0])
        if prompt in ('0', '1', '2'):ready.wait(timeout=5)
        assert gate.wait(5)
        (tmp_path/(prompt+'.html')).write_text(prompt)
        with lock:active[0] -= 1
        return {'summary':prompt}
    pool = WorkflowWorkers(tmp_path, runner, lambda:None, concurrency=3)
    try:
        jobs = [pool.submit(str(i)) for i in range(5)]
        ready.wait(timeout=5)
        assert pool.submit('0')['worker_id'] == jobs[0]['worker_id']
        assert sum(r['status']=='running' for r in pool.poll()) == 3
        gate.set()
        rows = settled(pool,5)
        assert maximum == [3]
        assert all(r['status']=='succeeded' for r in rows)
        assert len(list(tmp_path.glob('*.html'))) == 5
        assert all(json.loads(f.read_text())['status']=='succeeded' for f in (tmp_path/'.host/workers').glob('*.json'))
    finally:gate.set();pool.close()


def test_global_limit_applies_across_projects_and_slots_return_after_failure(tmp_path):
    slots = threading.BoundedSemaphore(2)
    lock = threading.Lock();active,maximum = [0],[0]
    def runner(prompt, **kw):
        with lock:active[0]+=1;maximum[0]=max(maximum[0],active[0])
        try:
            time.sleep(.05)
            if prompt=='bad':raise ValueError('frame failed')
            return {'summary':prompt}
        finally:
            with lock:active[0]-=1
    pools=[WorkflowWorkers(tmp_path/str(i),runner,lambda:None,concurrency=3,slots=slots) for i in range(2)]
    try:
        for pool in pools:
            for prompt in ('bad','good','next'):pool.submit(prompt)
        for pool in pools:
            rows=settled(pool,3)
            assert sorted(r['status'] for r in rows)==['failed','succeeded','succeeded']
        assert maximum==[2]
        assert slots.acquire(blocking=False) and slots.acquire(blocking=False)
        slots.release();slots.release()
    finally:
        for pool in pools:pool.close()


def test_closing_pool_cancels_active_and_queued_without_starting_more_work(tmp_path):
    started=threading.Event();calls=[]
    def runner(prompt, *, cancel_event, **kw):
        calls.append(prompt);started.set()
        assert cancel_event.wait(5)
        raise RuntimeError('HYPERFRAMES_CANCELED')
    pool=WorkflowWorkers(tmp_path,runner,lambda:None,concurrency=1)
    pool.submit('first');pool.submit('queued')
    assert started.wait(5)
    pool.close()
    assert calls==['first']
    assert all(row['status']=='canceled' for row in pool.jobs.values())


def test_poll_preserves_full_native_report_without_replaying_it_into_context(tmp_path):
    report={'summary':'native inspection details\n'*10000}
    pool=WorkflowWorkers(tmp_path,lambda *args,**kwargs:report,lambda:None)
    try:
        pool.submit('one frame')
        row=settled(pool,1)[0]
        assert row['status']=='succeeded' and 'result' not in row
        assert json.loads(Path(row['result_file']).read_text())['result']==report
        assert pool.poll()[0]==row
    finally:pool.close()


def test_batch_dispatch_preserves_roles_and_cannot_finish_while_workers_active(tmp_path):
    gate=threading.Event();calls=[]
    role=tmp_path/'role.md';role.write_text('FULL ROLE')
    def runner(prompt,**kw):
        calls.append(prompt);gate.wait(5)
        return {'summary':'done'}
    tools=WorkflowTools(tmp_path,lambda:None,runner=runner)
    try:
        outcome=tools.call('run_workers',{'workers':[{'role_file':str(role),'dispatch_context':str(i)} for i in range(3)]})
        assert outcome['ok'] and len(outcome['workers'])==3
        (tmp_path/'index.html').write_text('x');(tmp_path/'video.mp4').write_bytes(b'x')
        assert 'still active' in tools.call('complete_project',{'project_directory':str(tmp_path),'video_path':str(tmp_path/'video.mp4')})['error']
        gate.set();settled(tools.workers,3)
        assert sorted(calls)==['FULL ROLE\n\n## Dispatch context\n'+str(i) for i in range(3)]
        assert tools.call('complete_project',{'project_directory':str(tmp_path),'video_path':str(tmp_path/'video.mp4')})['ok']
    finally:gate.set();tools.close()


def test_parallel_sandbox_commands_have_private_persistent_tmp(tmp_path):
    tools=[WorkflowTools(tmp_path,lambda:None,worker=True,worker_id=str(i)) for i in range(3)]
    def run(i):
        t=tools[i]
        result=finish(t,t.call('run_command',{'command':f"printf '{i}' > /tmp/shared-name.txt; sleep .3; cat /tmp/shared-name.txt"}))
        assert result['output']==str(i)
        assert t.call('read_file',{'path':'/tmp/shared-name.txt'})['content']==str(i)
    try:
        with ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(run,range(3)))
    finally:
        for t in tools:t.close()


def test_edit_file_rejects_ambiguous_match_and_preserves_workspace_boundary(tmp_path):
    t=WorkflowTools(tmp_path,lambda:None)
    p=tmp_path/'frame.md';p.write_text('first\nsecond\nfirst')
    try:
        assert not t.call('edit_file',{'path':str(p),'old_text':'first','new_text':'bad'})['ok']
        assert p.read_text()=='first\nsecond\nfirst'
        assert t.call('edit_file',{'path':str(p),'old_text':'second','new_text':'correct'})['ok']
        assert p.read_text()=='first\ncorrect\nfirst'
        assert not t.call('edit_file',{'path':'/etc/passwd','old_text':'x','new_text':'y'})['ok']
    finally:t.close()


def test_concurrent_previews_allocate_distinct_ports_and_serve_own_tmp(tmp_path):
    tools=[WorkflowTools(tmp_path,lambda:None,worker=True,worker_id=str(i)) for i in range(3)]
    def serve(i):
        t=tools[i]
        t.call('write_file',{'path':'/tmp/index.html','content':f'worker {i}'})
        result=t.call('start_preview',{'directory':'/tmp'})
        assert result['ok'],result
        with urllib.request.urlopen(result['preview_url'],timeout=5) as response:
            assert response.read().decode()==f'worker {i}'
        assert t.call('start_preview',{'directory':'/tmp'})['preview_url']==result['preview_url']
        return result['preview_url']
    try:
        with ThreadPoolExecutor(max_workers=3) as pool:urls=list(pool.map(serve,range(3)))
        assert len(set(urls))==3
    finally:
        for t in tools:t.close()
    for url in urls:
        with pytest.raises(OSError):
            urllib.request.urlopen(url,timeout=1)
