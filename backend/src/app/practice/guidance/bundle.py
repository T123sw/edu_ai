from __future__ import annotations
import hashlib
import json
import subprocess
import shutil
from uuid import uuid4
from functools import lru_cache
from pathlib import Path
from threading import RLock

ROOT = Path(__file__).resolve().parents[5]
SOURCE = ROOT/'frontend/src/practice/guidance'
_lock = RLock()

def engine_digest():
    return hashlib.sha256((SOURCE/'model.ts').read_bytes()+(SOURCE/'replay.ts').read_bytes()).hexdigest()[:20]

def bundle(entry):
    digest=engine_digest() if entry=='replay' else hashlib.sha256((SOURCE/'model.ts').read_bytes()+(SOURCE/'runtime.ts').read_bytes()).hexdigest()[:20]
    return _build(entry,digest)

@lru_cache(maxsize=8)
def _build(entry,digest):
    with _lock:
        node=shutil.which('node')
        if not node: raise RuntimeError('分步实验运行库需要 Node.js')
        target=ROOT/'.runtime/practice-guidance'/f'{entry}-{digest}.{"mjs" if entry=="replay" else "js"}'
        target.parent.mkdir(parents=True,exist_ok=True)
        if not target.exists():
            build='const esbuild=require("esbuild");esbuild.buildSync(JSON.parse(process.argv[1]))'
            temporary=target.with_name(target.name+'.'+uuid4().hex+'.tmp')
            options={'entryPoints':[str(SOURCE/f'{entry}.ts')],'outfile':str(temporary),'bundle':True,'platform':'node' if entry=='replay' else 'browser','format':'esm' if entry=='replay' else 'iife','target':'es2022','minify':True}
            try:
                subprocess.run([node,'-e',build,json.dumps(options)],cwd=ROOT/'frontend',check=True,capture_output=True,timeout=30)
                temporary.replace(target)
            finally:
                temporary.unlink(missing_ok=True)
        return target

def replay(manifest,state=None,commands=None):
    digest=manifest.get('engine')
    if digest and digest!=engine_digest():
        import re
        if not re.fullmatch('[a-f0-9]{20}',digest):raise ValueError('实验引擎版本无效')
        engine=ROOT/'.runtime/practice-guidance'/f'replay-{digest}.mjs'
        if not engine.exists():raise ValueError('此实验需要的运行版本未安装，请恢复对应版本')
    else:engine=bundle('replay')
    result=subprocess.run([shutil.which('node'),str(engine)],input=json.dumps({'manifest':manifest,'state':state,'commands':commands or []}),capture_output=True,text=True,timeout=10)
    if result.returncode: raise ValueError('分步操作记录不能重放')
    return json.loads(result.stdout)
