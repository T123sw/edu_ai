#!/usr/bin/env python3
"""Run as the service owner; sudo authenticates before any deployment change."""
from pathlib import Path
import json
import os
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
VALUES = {'COURSE_PREPARATION_RESOURCE_CONCURRENCY':'8','COURSE_PREPARATION_VIDEO_CONCURRENCY':'8',
          'DURABLE_JOB_LIGHT_WORKERS':'2','HYPERFRAMES_GLOBAL_FRAME_CONCURRENCY':'16',
          'HYPERFRAMES_RENDER_CONCURRENCY':'4','HYPERFRAMES_RENDER_WORKERS':'4',
          'HYPERFRAMES_RENDER_MIN_FREE_MB':'2048','TTS_REMOTE_CONCURRENCY':'8',
          'TTS_REMOTE_REQUESTS_PER_SECOND':'4'}


def main():
    # Never drain a working service before discovering missing privileges.
    subprocess.run(['sudo','-v'], check=True)
    from dotenv import load_dotenv
    from sqlalchemy import create_engine, text
    load_dotenv(ROOT/'.env')
    with create_engine(os.environ['DATABASE_URL']).connect() as connection:
        count = connection.execute(text("SELECT count(*) FROM durable_tasks WHERE status IN ('pending','leased')")).scalar_one()
        if count:
            raise RuntimeError('Wait for pending/running work to drain before deployment; no tasks were interrupted')
    subprocess.run(['systemctl','--user','stop','edu-ai-durable-workers.service'], check=True)
    # Stop the API before updating configuration so no old process can claim new
    # jobs during the switch. The queue persists jobs already accepted.
    subprocess.run(['sudo','systemctl','stop','edu-ai-backend.service'], check=True)
    path = ROOT/'.env'
    lines = path.read_text().splitlines()
    seen = set()
    for i, line in enumerate(lines):
        key = line.split('=',1)[0].strip()
        if key in VALUES:
            lines[i] = key+'='+VALUES[key]; seen.add(key)
    lines.extend(key+'='+value for key,value in VALUES.items() if key not in seen)
    path.write_text('\n'.join(lines)+'\n')
    subprocess.run(['sudo','systemctl','start','edu-ai-backend.service'], check=True)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for _ in range(60):
        try:
            with opener.open('http://127.0.0.1:8001/health',timeout=2) as response:
                if response.status == 200: break
        except OSError:
            time.sleep(1)
    else:
        raise RuntimeError('Backend health check failed; supplementary workers remain stopped')
    subprocess.run(['systemctl','--user','start','edu-ai-durable-workers.service'], check=True)
    print(json.dumps({'status':'restarted','configuration':VALUES}))


if __name__ == '__main__':
    main()
