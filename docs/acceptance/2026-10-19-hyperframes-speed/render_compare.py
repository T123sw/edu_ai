import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import time
from core.config import Config
from app.integrations.hyperframes.workflow_agent import WorkflowTools
from app.integrations.hyperframes.runtime import RUNTIME

root = Path('/home/zxqs_ep/data/main-review/hyperframes-speed-20261019')
source = Path('/home/zxqs_ep/data/edu_ai/course_data/hyperframes/workflows/026f506184b04a256c6c9f60b27051c32effce941681fc0b7d6778e020d6b261/videos/bubble-sort-explained')
root.mkdir(parents=True, exist_ok=True)
results = []
for name, flags in [('baseline', ['--low-memory-mode']), ('two-workers', ['--no-low-memory-mode', '--workers', '2'])]:
    workspace = root / ('render-' + name)
    project = workspace / 'video'
    shutil.copytree(source, project, ignore=shutil.ignore_patterns('renders', 'exports', 'history', 'artifacts'), dirs_exist_ok=True)
    tools = WorkflowTools(workspace, lambda: None)
    try:
        command = 'cd ' + shlex.quote(str(project)) + ' && ' + shlex.join([shutil.which('node'), str(RUNTIME/'node_modules/hyperframes/dist/cli.js'), 'render', '--skill=faceless-explainer', '--quality', 'high', *flags, '--output', 'renders/comparison.mp4'])
        start = time.monotonic()
        result = tools.call('run_command', {'command': command})
        print(json.dumps({'phase': name, 'status': 'running'}), flush=True)
        while result.get('exit_code') is None:
            if time.monotonic()-start > 1200: raise TimeoutError(name)
            result = tools.call('poll_command', {'command_id': result['command_id']})
        elapsed = time.monotonic()-start
        if result['exit_code'] != 0: raise RuntimeError(result)
        video = project / 'renders/comparison.mp4'
        probe = json.loads(subprocess.check_output(['/usr/bin/ffprobe','-v','error','-show_entries','format=duration:stream=codec_type,width,height,r_frame_rate','-of','json', str(video)]))
        subprocess.run(['/usr/bin/ffmpeg','-v','error','-i',str(video),'-f','null','-'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        row = {'name':name,'elapsed_seconds':round(elapsed,2),'probe':probe,'decoded':True,'video':str(video),'log':result['output_file'], 'render_summary':result['output'][-2400:]}
        results.append(row)
        (root/'render-comparison.json').write_text(json.dumps(results,indent=2))
        print(json.dumps({'phase':name,'status':'passed','seconds':row['elapsed_seconds']}),flush=True)
    finally: tools.close()
