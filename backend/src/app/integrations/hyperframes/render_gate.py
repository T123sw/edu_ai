"""Invoke the intact native CLI with one host-wide render permit."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

if __package__:
    from .stage_limits import StageSlots
else:
    from stage_limits import StageSlots


def available_memory():
    available = next((int(line.split()[1]) * 1024 for line in Path('/proc/meminfo').read_text().splitlines()
                      if line.startswith('MemAvailable:')), 0)
    for root in (Path('/sys/fs/cgroup'),):
        try:
            maximum = (root / 'memory.max').read_text().strip()
            if maximum != 'max':
                available = min(available, max(0, int(maximum) - int((root / 'memory.current').read_text())))
        except OSError:
            pass
    return available


def main():
    command = sys.argv[1:]
    if len(command) < 2:
        raise ValueError('Expected native CLI command')
    if 'render' not in command[2:] or os.getenv('EDU_RENDER_PERMIT') == '1':
        return subprocess.call(command)
    slots = StageSlots('hyperframes-render', int(os.getenv('HYPERFRAMES_RENDER_CONCURRENCY', '4')))
    minimum = int(os.getenv('HYPERFRAMES_RENDER_MIN_FREE_MB', '2048')) * 1024 * 1024
    queued = time.monotonic()
    print(json.dumps({'stage': 'render', 'status': 'queued', 'at': time.time()}), flush=True)
    while True:
        slots.acquire()
        if available_memory() >= minimum:
            break
        slots.release()
        time.sleep(.5)
    process = None
    try:
        print(json.dumps({'stage': 'render', 'status': 'running', 'wait_seconds': time.monotonic()-queued}), flush=True)
        # Child inherits the lock, so even wrapper termination cannot admit an
        # extra render while the surviving native process still owns the permit.
        process = subprocess.Popen(command, pass_fds=(slots.fileno(),), env={**os.environ, 'EDU_RENDER_PERMIT': '1'})
        def stop(signum, frame):
            if process.poll() is None:
                process.send_signal(signum)
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, stop)
        return process.wait()
    finally:
        if process is not None and process.poll() is None:
            process.kill()
            process.wait()
        slots.release()


if __name__ == '__main__':
    sys.exit(main())
