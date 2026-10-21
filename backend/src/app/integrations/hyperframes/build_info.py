"""Fingerprint captured at import, never relabel an old process after edits."""
import hashlib
import os
from pathlib import Path
import time

_ROOT = Path(__file__).parent
BUILD_ID = hashlib.sha256(b''.join(p.name.encode() + p.read_bytes() for p in sorted(_ROOT.iterdir())
    if p.suffix in ('.py', '.mjs', '.cjs'))).hexdigest()[:20]
LOADED_AT = time.time()


def runtime_info():
    defaults = {'COURSE_PREPARATION_RESOURCE_CONCURRENCY':'8', 'COURSE_PREPARATION_VIDEO_CONCURRENCY':'8',
        'HYPERFRAMES_FRAME_CONCURRENCY':'6', 'HYPERFRAMES_GLOBAL_FRAME_CONCURRENCY':'16',
        'HYPERFRAMES_RENDER_WORKERS':'4', 'HYPERFRAMES_RENDER_CONCURRENCY':'4',
        'TTS_REMOTE_CONCURRENCY':'8', 'TTS_REMOTE_REQUESTS_PER_SECOND':'4'}
    return {'build_id':BUILD_ID, 'loaded_at':LOADED_AT, 'pid':os.getpid(),
            'stage_limits_scope':'shared-host', 'configuration':{k:os.getenv(k,v) for k,v in defaults.items()}}
