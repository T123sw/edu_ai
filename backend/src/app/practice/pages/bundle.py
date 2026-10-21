import hashlib
import json
import shutil
import subprocess
from uuid import uuid4
from ..experiment.bundle import ROOT, SOURCE

def bundle():
    sources = ['pagesRuntime.ts', 'pagesModel.ts', 'model.ts']
    revision = hashlib.sha256(b''.join((SOURCE / s).read_bytes() for s in sources)).hexdigest()
    target = ROOT / '.runtime/practice-pages' / f'{revision}.js'
    if target.exists(): return target
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix('.' + uuid4().hex + '.tmp')
    try:
        options = {'entryPoints': [str(SOURCE / sources[0])], 'outfile': str(temporary), 'bundle': True, 'platform': 'browser', 'format': 'iife', 'target': 'es2022', 'minify': True}
        subprocess.run([shutil.which('node') or 'node', '-e', 'require("esbuild").buildSync(JSON.parse(process.argv[1]))', json.dumps(options)], cwd=ROOT / 'frontend', check=True, capture_output=True, timeout=30)
        temporary.replace(target)
    finally: temporary.unlink(missing_ok=True)
    return target
