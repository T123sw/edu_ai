"""Persist a stage's exact pytest output and execution metadata without shell piping."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage', required=True)
    parser.add_argument('tests', nargs='+')
    args, pytest_options = parser.parse_known_args()
    root = Path(__file__).resolve().parents[3]
    output = root / 'docs/acceptance/staged-agent-implementation' / args.stage
    output.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    command = [sys.executable, '-m', 'pytest', *args.tests, *pytest_options, '-q']
    started = datetime.now(timezone.utc)
    result = subprocess.run(command, cwd=root / 'backend/src', stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    log = output / f'{stamp}-pytest.txt'
    log.write_bytes(result.stdout)
    record = {'started_at': started.isoformat(), 'finished_at': datetime.now(timezone.utc).isoformat(),
              'command': command, 'exit_code': result.returncode, 'log': log.name,
              'sha256': hashlib.sha256(result.stdout).hexdigest(),
              'base_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root).decode().strip(),
              'python': sys.version.split()[0]}
    (output / f'{stamp}-run.json').write_text(json.dumps(record, indent=2) + '\n')
    print('\n'.join(result.stdout.decode(errors='replace').splitlines()[-45:]))
    print('Saved:', log)
    raise SystemExit(result.returncode)


if __name__ == '__main__':
    main()
