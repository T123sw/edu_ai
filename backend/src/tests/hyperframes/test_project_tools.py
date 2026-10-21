"""Host policy/cache tests; native browser evidence is recorded separately."""
import json
import os
from pathlib import Path
import subprocess

import pytest

from app.integrations.hyperframes.workflow_agent import HOST, WorkflowTools


@pytest.fixture
def environment(tmp_path):
    runtime = tmp_path/'runtime'
    cli = runtime/'node_modules/hyperframes/dist/cli.js'
    cli.parent.mkdir(parents=True)
    (cli.parent.parent/'package.json').write_text('{"version":"fixture"}')
    cli.write_text('''const fs=require('fs');
fs.appendFileSync('calls.txt','called\\n');
const report=JSON.parse(fs.readFileSync('fixture-report.json'));
console.log(JSON.stringify(report));process.exit(report.ok?0:1);
''')
    for name,body in [('assets/fonts/NotoSansSC-Variable.ttf',b'fixture font'),
                      ('assets/fonts/OFL-NotoSansSC.txt',b'fixture license'),
                      ('node_modules/gsap/dist/gsap.min.js',b'fixture gsap')]:
        file=runtime/name;file.parent.mkdir(parents=True,exist_ok=True);file.write_bytes(body)
    project=tmp_path/'project';project.mkdir()
    (project/'index.html').write_text('<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>')
    report={'ok':False,'browserSkipped':False,**{key:{'ok':True,'findings':[]} for key in ['lint','runtime','motion','contrast']},
            'layout':{'ok':False,'samples':[1],'findings':[{'code':'text_box_overflow'}]}}
    (project/'fixture-report.json').write_text(json.dumps(report))
    # Native output is excluded from the check fingerprint, as it is in production.
    cli.write_text(cli.read_text().replace("'calls.txt'", "'.hyperframes/calls.txt'"))
    (project/'.hyperframes').mkdir()
    def invoke(action):
        result=subprocess.run(['node',str(HOST/'project_tools.mjs'),action,str(project)],
            env={**os.environ,'EDU_HF_RUNTIME':str(runtime)},text=True,capture_output=True)
        return result,json.loads(result.stdout) if result.stdout.strip() else None
    return project,report,invoke


def test_prepare_preserves_native_files_and_localizes_gsap(environment):
    project,_,invoke=environment
    (project/'frame.md').write_text('Original native design')
    result,assets=invoke('prepare')
    assert result.returncode==0,result.stderr
    assert assets['font_family']=='Noto Sans SC'
    assert 'assets/gsap.min.js' in (project/'index.html').read_text()
    assert (project/'assets/fonts/NotoSansSC-Variable.ttf').read_bytes()==b'fixture font'
    assert (project/'frame.md').read_text()=='Original native design'
    before=(project/'assets/fonts/NotoSansSC-Variable.ttf').stat().st_mtime_ns
    invoke('prepare')
    assert (project/'assets/fonts/NotoSansSC-Variable.ttf').stat().st_mtime_ns==before


def test_check_advisory_does_not_block_and_unchanged_inputs_are_cached(environment):
    project,_,invoke=environment
    first,a=invoke('check');second,b=invoke('check')
    assert first.returncode==second.returncode==0
    assert a['passed'] and a['advisory_count']==1
    assert b['cached']
    assert (project/'.hyperframes/calls.txt').read_text().count('called')==1
    (project/'index.html').write_text('changed composition')
    _,c=invoke('check')
    assert not c['cached'] and c['digest']!=a['digest']
    assert (project/'.hyperframes/calls.txt').read_text().count('called')==2


def test_check_retains_blocking_failures_and_rechecks_actual_fix(environment):
    project,report,invoke=environment
    report['runtime']={'ok':False,'findings':[{'code':'script_error'}]}
    (project/'fixture-report.json').write_text(json.dumps(report))
    result,a=invoke('check')
    assert result.returncode==1 and not a['passed']
    assert a['blocking'][0]['section']=='runtime'
    result,b=invoke('check')
    assert result.returncode==1 and b['cached'] and not b['passed']
    report['runtime']={'ok':True,'findings':[]}
    (project/'fixture-report.json').write_text(json.dumps(report))
    result,c=invoke('check')
    assert result.returncode==0 and c['passed'] and not c['cached']


def test_incomplete_browser_check_does_not_record_success(environment):
    project,report,invoke=environment
    report['browserSkipped']=True
    (project/'fixture-report.json').write_text(json.dumps(report))
    result,_=invoke('check')
    assert result.returncode==2
    assert not (project/'.hyperframes/host-check.json').exists()


def test_only_parent_advertises_shared_assets_and_inspection_tools(tmp_path):
    parent=WorkflowTools(tmp_path,lambda:None)
    worker=WorkflowTools(tmp_path,lambda:None,worker=True,worker_id='one')
    try:
        parent_names={s['name'] for s in parent.schemas()}
        worker_names={s['name'] for s in worker.schemas()}
        assert {'prepare_project','check_project','start_preview','inspect_image'} <= parent_names
        assert not {'prepare_project','check_project','start_preview','inspect_image'} & worker_names
        assert {'read_file','write_file','edit_file','run_command','finish_work'} <= worker_names
    finally:
        parent.close();worker.close()
