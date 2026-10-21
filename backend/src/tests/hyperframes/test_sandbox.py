import json
import os
from pathlib import Path
import shutil
import subprocess
import pytest
from app.integrations.hyperframes.sandbox import isolated_command
from app.integrations.hyperframes.runtime import RUNTIME, run_process


def test_missing_boundary_fails_closed(monkeypatch,tmp_path):
    monkeypatch.setenv('HYPERFRAMES_BWRAP_PATH',str(tmp_path/'absent'))
    with pytest.raises(RuntimeError,match='bubblewrap'):
        isolated_command(['/usr/bin/node','cli'],runtime=tmp_path,project=tmp_path)


def test_real_namespace_hides_secrets_host_files_and_network(monkeypatch,tmp_path):
    binary=os.environ.get('HYPERFRAMES_BWRAP_PATH') or shutil.which('bwrap')
    node=shutil.which('node')
    if not binary or not node: pytest.skip('requires installed bubblewrap and Node')
    secret=tmp_path/'private';secret.write_text('private')
    project=tmp_path/'project';project.mkdir()
    script=project/'test.js'
    script.write_text('''const fs=require('fs'),net=require('net');
const result={secret:process.env.TEST_SECRET,hostFile:fs.existsSync(process.argv[2])};
const socket=net.connect({host:'1.1.1.1',port:80});
socket.on('error',()=>{result.network=false;console.log(JSON.stringify(result));});
socket.on('connect',()=>{result.network=true;console.log(JSON.stringify(result));socket.end();});
setTimeout(()=>process.exit(3),2000).unref();''')
    monkeypatch.setenv('TEST_SECRET','must-not-leak')
    command,env=isolated_command([node,str(script),str(secret)],runtime=RUNTIME,project=project)
    value=json.loads(run_process(command,env=env,timeout=10))
    assert value=={'hostFile':False,'network':False}
