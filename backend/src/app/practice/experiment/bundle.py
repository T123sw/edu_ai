"""Content-addressed browser runtime; MAIC-UI supplies only domain simulation."""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[5]
SOURCE = ROOT / 'frontend/src/practice/experiment'

def bundle():
    digest = hashlib.sha256(b''.join((SOURCE / name).read_bytes() for name in ['model.ts', 'runtime.ts'])).hexdigest()
    target = ROOT / '.runtime/practice-experiment' / f'{digest}.js'
    if target.exists(): return target
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix('.' + uuid4().hex + '.tmp')
    options = {'entryPoints': [str(SOURCE / 'runtime.ts')], 'outfile': str(temporary), 'bundle': True, 'platform': 'browser', 'format': 'iife', 'target': 'es2022', 'minify': True}
    try:
        subprocess.run([shutil.which('node') or 'node', '-e', 'require("esbuild").buildSync(JSON.parse(process.argv[1]))', json.dumps(options)], cwd=ROOT / 'frontend', check=True, capture_output=True, timeout=30)
        temporary.replace(target)
    finally: temporary.unlink(missing_ok=True)
    return target
