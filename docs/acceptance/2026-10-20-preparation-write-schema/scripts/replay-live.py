"""Inject missing-envelope output, then let the real model correct it; no task writes."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'backend/src'))
import dotenv
import httpx
from app.chat.harness.content_gateway import ContentGateway
from app.chat.harness.preparation_content import CONTENT_INSTRUCTIONS
from app.chat.harness.preparation_write_contract import bind_write_contract
from app.course_preparation.harness_generation import PreparationHarnessGateway
from tests.course_preparation.test_generated_content_constraints import payload
from tests.course_preparation.test_harness_generation import Ledger
from tests.course_preparation.test_preparation_write_schema import response

OUT = Path(__file__).resolve().parents[1]
settings = dotenv.dotenv_values(ROOT / '.env')
configured = ContentGateway(api_base=settings['DEEPSEEK_BASE_URL'],
    api_key=settings['DEEPSEEK_API_KEY'], model_name=settings.get('LLM_MODEL') or 'deepseek-v4-pro')
request = payload('quiz')
fixture = json.loads((OUT / 'native-quiz-example_first.json').read_text())
request.teaching_context = fixture['teaching_context']
calls, ledger = [], Ledger()

def complete(http_request):
    body = json.loads(http_request.content)
    record = {'index': len(calls), 'source': 'injected_missing_envelope' if not calls else 'real_provider'}
    calls.append(record)
    if len(calls) == 1:
        (OUT / 'quiz-write-schema.json').write_text(json.dumps(
            body['tools'][0]['function']['parameters'], ensure_ascii=False, indent=2) + '\n')
        return response(body, fixture['artifact']['content'])
    record['feedback'] = body['messages'][-1]['content']
    assert '未执行' in record['feedback']
    started = time.monotonic()
    with httpx.Client(timeout=httpx.Timeout(80, connect=10)) as client:
        result = client.post(str(http_request.url), headers=dict(http_request.headers), content=http_request.content)
    record.update(seconds=time.monotonic() - started, http_status=result.status_code)
    return result

root = PreparationHarnessGateway(configured, ledger,
    {'artifact_id': 'isolated-write-contract-replay', 'spec_digest': request.spec_digest},
    deadline=(datetime.now(timezone.utc) + timedelta(minutes=3)).isoformat(),
    client_factory=lambda **kw: httpx.Client(transport=httpx.MockTransport(complete), **kw))
writer = bind_write_contract(root.for_phase('resource_write', context={
    **request.teaching_context, 'response_format': 'json'}), 'quiz',
    request.teaching_context, request.spec_digest)
started = time.monotonic()
result = {'production_task_mutated': False, 'injected_response_count': 1,
          'scope': 'Schema recovery only; content review is separately covered by native tests.'}
try:
    output = writer.chat([
        {'role': 'system', 'content': CONTENT_INSTRUCTIONS},
        {'role': 'user', 'content': json.dumps({
            'resource_type': 'quiz', 'teaching_context': request.teaching_context,
            'evidence': '模型输出工具名与参数，程序校验名称、权限和参数后执行。add(a=12,b=30)=42；缺少 b 时校验失败，工具不执行。',
        }, ensure_ascii=False)},
    ], max_tokens=12000)
    result.update(status='recovered', envelope=json.loads(output))
except Exception as exc:
    result.update(status='failed', error=type(exc).__name__, message=str(exc))
result.update(seconds=time.monotonic() - started, calls=calls, actions=[
    {key: action['receipt']['model_response'].get(key)
     for key in ('model', 'phase', 'protocol_recovery_attempt')}
    for action in ledger.actions])
(OUT / 'live-replay.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({k: v for k, v in result.items() if k not in ('envelope', 'calls')}, ensure_ascii=False))
assert result['status'] == 'recovered'
assert len(calls) >= 2 and result['actions'][1]['protocol_recovery_attempt'] == 1
