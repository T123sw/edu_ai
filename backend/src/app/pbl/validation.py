"""Isolated browser validation using exactly the same Worker runtime as Sandpack."""
import json
import os
from pathlib import Path
import signal
import subprocess
from .schemas import GeneratedExerciseCandidate, TEMPLATE_VERSION

FRONTEND=Path(__file__).resolve().parents[4]/'frontend'

class RuntimeUnavailable(RuntimeError):
    pass

def validate_candidate(candidate: GeneratedExerciseCandidate) -> dict:
    payload=json.dumps({'candidate':candidate.model_dump(mode='json'),'templateVersion':TEMPLATE_VERSION},ensure_ascii=False)
    process=subprocess.Popen(['node','--import','tsx','scripts/validate-pbl.mjs'],cwd=FRONTEND,
        stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
    try:
        out,err=process.communicate(payload,timeout=75)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid,signal.SIGKILL)
        process.communicate()
        raise RuntimeUnavailable('浏览器检查超时，请检查运行环境') from None
    if process.returncode:
        # stderr can include source fragments; never expose it in public job errors.
        raise RuntimeUnavailable('浏览器检查未能启动，请确认 Node 与 Playwright Chromium 已安装')
    try: result=json.loads(out)
    except (ValueError,TypeError): raise RuntimeUnavailable('浏览器检查返回无效结果') from None
    if not isinstance(result,dict) or not isinstance(result.get('passed'),bool):
        raise RuntimeUnavailable('浏览器检查返回无效结果')
    return result
