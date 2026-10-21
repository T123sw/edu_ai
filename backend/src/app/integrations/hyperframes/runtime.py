"""Native CLI boundary. Cancellation always tears down the process group."""
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import time

REPOSITORY = Path(__file__).resolve().parents[5]
RUNTIME = Path(os.environ.get('HYPERFRAMES_RUNTIME_DIR', REPOSITORY / 'hyperframes-runtime'))
UPSTREAM = REPOSITORY / 'vendor' / 'hyperframes'


def run_process(args, *, cwd=None, canceled=None, timeout=1800, env=None, accepted_exit_codes=(0,)):
    with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
        process = subprocess.Popen([str(a) for a in args], cwd=cwd, stdout=output,
                                   stderr=errors, start_new_session=True, env=env)
        start = time.monotonic()
        try:
            while process.poll() is None:
                if canceled and canceled(): raise RuntimeError('HYPERFRAMES_CANCELED')
                if time.monotonic() - start > timeout: raise TimeoutError('HyperFrames subprocess timeout')
                time.sleep(.1)
            output.seek(0)
            message = output.read().decode(errors='replace')
            if process.returncode not in accepted_exit_codes:
                errors.seek(0)
                diagnostic = message + errors.read().decode(errors='replace')
                raise RuntimeError(f'HyperFrames command failed ({process.returncode}): {diagnostic[-24000:]}')
            return message
        finally:
            # Children can survive their parent: always address the dedicated group.
            try: os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError: pass
            try: process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                try: os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError: pass
                process.wait(timeout=3)
            try: os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError: pass


class NativeRuntime:
    def __init__(self, *, canceled=None):
        self.canceled = canceled

    def cli(self, *args):
        node = shutil.which('node')
        cli = RUNTIME / 'node_modules/hyperframes/dist/cli.js'
        if not node or not cli.is_file(): raise RuntimeError('Install pinned hyperframes-runtime dependencies and Node >=22')
        from .sandbox import isolated_command
        host = Path(__file__).parent
        command, environment = isolated_command([node, cli, *args], runtime=RUNTIME, project=args[1], read_only_roots=(host,))
        if args[0] == 'render':
            from .stage_limits import limit_root
            root = limit_root()
            marker = command.index('--')
            command[marker:marker] = ['--bind', str(root), str(root)]
            environment.update(EDU_HF_RUNTIME=str(RUNTIME), EDU_STAGE_LIMIT_DIR=str(root),
                NODE_OPTIONS='--require='+str(host/'render_guard.cjs'),
                HYPERFRAMES_RENDER_CONCURRENCY=os.getenv('HYPERFRAMES_RENDER_CONCURRENCY', '4'),
                HYPERFRAMES_RENDER_MIN_FREE_MB=os.getenv('HYPERFRAMES_RENDER_MIN_FREE_MB', '2048'))
        # Native check returns 1 for reported quality findings as well as failures.
        # Parse that report below; crashes and other commands still fail normally.
        return run_process(command, canceled=self.canceled, env=environment,
                           accepted_exit_codes=(0, 1) if args[0] == 'check' else (0,))

    def check(self, directory):
        # `check` already includes lint. Use native midpoint sampling instead of
        # auditing every tween boundary, which amplified cosmetic false positives.
        checks = json.loads(self.cli('check', directory, '--json'))
        sections = ('lint', 'runtime', 'motion', 'layout', 'contrast')
        if (not isinstance(checks, dict) or checks.get('browserSkipped', True)
                or not checks.get('layout', {}).get('samples')
                or any(not isinstance(checks.get(k, {}).get('ok'), bool) for k in sections)):
            raise RuntimeError('Native browser checks incomplete: ' + json.dumps(checks))
        strict = os.environ.get('HYPERFRAMES_STRICT_VISUAL_CHECKS') == '1'
        blocking = sections if strict else ('lint', 'runtime', 'motion')
        if any(not checks[k]['ok'] for k in blocking):
            raise RuntimeError('Native playback checks failed: ' + json.dumps(checks))
        if not checks.get('ok') and all(checks[k]['ok'] for k in sections):
            raise RuntimeError('Unclassified native check failure: ' + json.dumps(checks))
        issues = [{**finding, 'section': section, 'blocking': False}
                  for section in ('layout', 'contrast')
                  for finding in checks[section].get('findings', [])]
        return {'lint': checks['lint'], 'check': checks, 'passed': True,
                'policy': 'strict' if strict else 'playback-first', 'issues': issues}

    def render(self, directory, destination):
        self.cli('render', directory, '--output', destination, '--format', 'mp4', '--low-memory-mode')
        info = self.probe(destination)
        if not any(s.get('codec_type') == 'audio' for s in info.get('streams', [])):
            raise RuntimeError('Rendered classroom has no audio stream')
        if not any(s.get('codec_type') == 'video' for s in info.get('streams', [])):
            raise RuntimeError('Rendered classroom has no video stream')
        return info

    def probe(self, path):
        return json.loads(run_process(['ffprobe', '-v', 'error', '-show_format', '-show_streams', '-of', 'json', path], canceled=self.canceled, timeout=60))

    def audio_duration(self, path):
        from .contracts import time_value
        info = self.probe(path)
        if not any(s.get('codec_type') == 'audio' for s in info.get('streams', [])): raise ValueError('Missing audio stream')
        duration = time_value(float(info['format']['duration']))
        if duration <= 0: raise ValueError('Empty audio')
        return duration
