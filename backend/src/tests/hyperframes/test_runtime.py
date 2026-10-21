import sys
import time
import pytest
from app.integrations.hyperframes.runtime import run_process
from app.integrations.hyperframes.runtime import NativeRuntime
import json

def test_failure_cancel():
    with pytest.raises(RuntimeError,match='details'):
        run_process([sys.executable,'-c','print("details");raise SystemExit(3)'])
    start=time.monotonic()
    with pytest.raises(RuntimeError,match='CANCELED'):
        run_process([sys.executable,'-c','import time;time.sleep(30)'],canceled=lambda:True)
    assert time.monotonic()-start<4

def test_timeout():
    with pytest.raises(TimeoutError): run_process([sys.executable,'-c','import time;time.sleep(30)'],timeout=.01)


def test_successful_json_output_is_not_corrupted_by_stderr_diagnostics():
    import json
    result=run_process([sys.executable,'-c',
        'import sys; print("browser diagnostic",file=sys.stderr); print(\'{"ok":true}\')'])
    assert json.loads(result)=={'ok':True}
    with pytest.raises(RuntimeError,match='browser failure'):
        run_process([sys.executable,'-c','import sys; print("browser failure",file=sys.stderr);sys.exit(2)'])


def test_native_quality_exit_keeps_report_but_crashes_still_fail():
    assert json.loads(run_process([sys.executable, '-c',
        'print(\'{"ok":false}\');raise SystemExit(1)'], accepted_exit_codes=(0, 1))) == {'ok': False}
    with pytest.raises(RuntimeError):
        run_process([sys.executable, '-c', 'raise SystemExit(2)'], accepted_exit_codes=(0, 1))


@pytest.fixture
def report():
    return {'ok': False, 'browserSkipped': False,
            'lint': {'ok': True}, 'runtime': {'ok': True}, 'motion': {'ok': True},
            'layout': {'ok': False, 'samples': [1, 2], 'findings': [
                {'code': 'content_overlap', 'severity': 'error'}]},
            'contrast': {'ok': True, 'findings': []}}


def test_cosmetic_findings_are_advisory_without_boundary_oversampling(monkeypatch, report):
    calls = []
    monkeypatch.delenv('HYPERFRAMES_STRICT_VISUAL_CHECKS', raising=False)
    def cli(self, *args):
        calls.append(args)
        return json.dumps(report)
    monkeypatch.setattr(NativeRuntime, 'cli', cli)
    result = NativeRuntime().check('/project')
    assert result['passed'] and not result['check']['ok']
    assert result['issues'][0]['code'] == 'content_overlap'
    assert not result['issues'][0]['blocking']
    assert calls == [('check', '/project', '--json')]


@pytest.mark.parametrize('failure', ['lint', 'runtime', 'motion', 'browser', 'strict'])
def test_playback_failures_and_explicit_strict_mode_still_block(monkeypatch, report, failure):
    if failure == 'strict': monkeypatch.setenv('HYPERFRAMES_STRICT_VISUAL_CHECKS', '1')
    elif failure == 'browser': report['browserSkipped'] = True
    else: report[failure]['ok'] = False
    monkeypatch.setattr(NativeRuntime, 'cli', lambda *args: json.dumps(report))
    with pytest.raises(RuntimeError): NativeRuntime().check('/project')
