"""Bounded anonymous browser checks; never execute student JavaScript in Python/Node."""
import json
import os
import signal
import subprocess
import threading
from .validation import FRONTEND, RuntimeUnavailable

_CAPACITY = threading.BoundedSemaphore(2)


def check_project(files: dict, checks: list[dict], *, runtime=None) -> dict:
    if not _CAPACITY.acquire(timeout=10):
        raise RuntimeUnavailable('检查服务繁忙，请稍后再试')
    try:
        try:
            process = subprocess.Popen(['node', 'scripts/check-pbl-project.mjs'], cwd=FRONTEND,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, start_new_session=True)
        except OSError:
            raise RuntimeUnavailable('浏览器检查环境不可用') from None
        try:
            output, _ = process.communicate(json.dumps({'files': files, 'checks': checks, **({'runtime':runtime} if runtime else {})}, ensure_ascii=False), timeout=180 if runtime else 90)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
            raise RuntimeUnavailable('检查超时，请检查代码中是否存在无限循环') from None
        if process.returncode:
            raise RuntimeUnavailable('浏览器检查环境不可用')
        try:
            report = json.loads(output)
            if not isinstance(report['passed'], bool) or len(report['results']) != len(checks):
                raise ValueError()
            return report
        except (ValueError, KeyError, TypeError):
            raise RuntimeUnavailable('浏览器检查返回了无效结果') from None
    finally:
        _CAPACITY.release()
