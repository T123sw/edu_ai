import multiprocessing as mp
import os
from pathlib import Path
import subprocess
import sys
import time

from app.integrations.hyperframes.stage_limits import StageSlots, ProviderRate


def _hold(root, ready, release):
    slots = StageSlots('test', 2, root=root)
    with slots.hold():
        ready.put(os.getpid())
        time.sleep(30)


def test_cross_process_limit_and_crash_recovery(tmp_path):
    ctx = mp.get_context('spawn')
    ready, release = ctx.Queue(), ctx.Event()
    children = [ctx.Process(target=_hold, args=(str(tmp_path), ready, release)) for _ in range(2)]
    try:
        for child in children: child.start()
        for _ in children: ready.get(timeout=10)
        slots = StageSlots('test', 2, root=tmp_path)
        assert not slots.acquire(blocking=False)
        children[0].kill(); children[0].join(5)
        assert slots.acquire(timeout=2)
        slots.release()
    finally:
        for child in children:
            if child.is_alive(): child.kill()
            child.join(5)


def test_rate_and_cooldown_shared_across_instances(tmp_path):
    a = ProviderRate('account', interval=.1, root=tmp_path)
    b = ProviderRate('account', interval=.1, root=tmp_path)
    assert a.try_start() == 0
    assert b.try_start() > 0
    a.cool_down(2)
    assert b.try_start() > 1
    b.cool_down(.01)
    assert a.try_start() > 1


def test_render_gate_limits_processes_and_releases_on_completion(tmp_path):
    from app.integrations.hyperframes import render_gate
    script = tmp_path/'fake-cli.py'
    script.write_text("import time;print('render-started',flush=True);time.sleep(.8)")
    env = {**os.environ, 'EDU_STAGE_LIMIT_DIR':str(tmp_path/'limits'),
           'HYPERFRAMES_RENDER_CONCURRENCY':'1', 'HYPERFRAMES_RENDER_MIN_FREE_MB':'0'}
    command = [sys.executable, render_gate.__file__, sys.executable, str(script), 'render']
    first = subprocess.Popen(command, env=env, stdout=subprocess.PIPE, text=True)
    try:
        while 'render-started' not in first.stdout.readline():
            assert first.poll() is None
        start = time.monotonic()
        second = subprocess.run(command, env=env, capture_output=True, text=True, timeout=10)
        assert second.returncode == 0, second.stderr
        assert time.monotonic() - start > 1.2
        assert 'render-started' in second.stdout
        first.wait(5)
    finally:
        if first.poll() is None: first.kill(); first.wait()


def test_direct_node_cli_also_waits_for_render_permit(tmp_path):
    from app.integrations.hyperframes import render_gate
    host = Path(render_gate.__file__).parent
    runtime = tmp_path/'runtime'
    cli = runtime/'node_modules/hyperframes/dist/cli.js'
    cli.parent.mkdir(parents=True)
    marker = tmp_path/'started'
    cli.write_text("require('fs').writeFileSync(process.env.TEST_RENDER_MARKER, 'started')")
    env = {**os.environ, 'EDU_STAGE_LIMIT_DIR':str(tmp_path/'limits'), 'EDU_HF_RUNTIME':str(runtime),
        'NODE_OPTIONS':'--require='+str(host/'render_guard.cjs'), 'HYPERFRAMES_RENDER_CONCURRENCY':'1',
        'HYPERFRAMES_RENDER_MIN_FREE_MB':'0', 'TEST_RENDER_MARKER':str(marker)}
    env.pop('EDU_RENDER_PERMIT', None)
    slots = StageSlots('hyperframes-render',1,root=tmp_path/'limits')
    slots.acquire()
    process = subprocess.Popen(['node',str(cli),'render'],env=env,stdout=subprocess.PIPE,text=True)
    try:
        time.sleep(.3)
        assert process.poll() is None
        assert not marker.exists()
        slots.release()
        output, _ = process.communicate(timeout=10)
        assert process.returncode == 0
        assert marker.exists() and '"status": "running"' in output
    finally:
        if getattr(slots.local,'file',None):slots.release()
        if process.poll() is None:process.kill();process.wait()
