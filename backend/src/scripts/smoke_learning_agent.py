"""Three real-model P3 questions, synthetic resources and an isolated PostgreSQL schema.

Requires explicit LEARNING_TEST_DATABASE_URL. Never migrates business tables.
Only redacted model metadata and synthetic Q/A are written to the report.
"""
import json
import os
from pathlib import Path
import time
from uuid import uuid4

TEST_URL = os.environ['LEARNING_TEST_DATABASE_URL']
from app.services.runtime_config_resolver import runtime_config_resolver
config = runtime_config_resolver.resolve('llm')
os.environ['LEARNING_TEST_DATABASE_URL'] = TEST_URL
os.environ['LEARNING_BROWSER_AGENT'] = '1'
from tests.self_learning import browser_app as fixture
from sqlalchemy import text
import httpx
from app.self_learning.model_adapter import LearningModelAdapter
from app.self_learning.agent_runtime import LearningAgentRuntime
from app.self_learning.turn_contracts import AnswerRequest

svc = fixture.svc
diagnostics = []
async def diagnose(response):
    if response.status_code >= 400:
        await response.aread()
        # This script submits synthetic fixture data only. Never record headers.
        detail = response.text[:1500]
        from core.config import Config
        for secret in (config.get('api_key'), Config.DEEPSEEK_API_KEY_BACKUP, Config.DEEPSEEK_API_KEY):
            if secret:
                detail = detail.replace(secret, '[REDACTED]')
        diagnostics.append({'status': response.status_code, 'detail': detail})
def client_factory(**kwargs):
    return httpx.AsyncClient(event_hooks={'response': [diagnose]}, **kwargs)
selected = 'return 把结果交回调用处，而 print 只负责输出文本。'
materials = [('a-core', 'a', '函数、参数与返回值', '# 函数\n\n函数接收参数并执行一段可复用的代码。\n\n' + selected + '\n\n示例：def square(x): return x * x。square(3) 得到 9。'),
    ('b-core', 'b', '闭包与词法作用域', '# 闭包\n\n闭包是函数与其引用的外部词法环境的组合。内部函数即使离开外部函数，也能读取被捕获的变量。\n\n示例：def make_adder(n):\n    def add(x): return x + n\n    return add\n\nmake_adder(2)(3) 的结果是 5。')]
report = {'model': config['model'], 'configuration_source': config.get('_source'), 'temperature': .2,
          'max_output_tokens': 2000, 'runtime_deadline_seconds': 90, 'questions': []}
try:
    for mid, node, title, content in materials:
        svc.manager.save_generated_material('learning-fixture', 'report', mid, {'title': title, 'content': content, 'learning_course_resource': True},
            owner_user_id='alice', visibility='course', scope_type='knowledge_point', scope_id=node)
    material = svc.material('learning-fixture', 'report', 'a-core', 'alice')
    runtime = LearningAgentRuntime(svc, svc.turn_repository, lambda _: LearningModelAdapter.from_config(config, client_factory))
    for question, selection in [
        ('用一个简单例子解释我选中的这句话。', selected),
        ('square(3) 为什么得到 9？只给一步提示，不要展开完整教程。', ''),
        ('请先查阅课程其他资料，再说明闭包是什么，并引用课程中的例子。', ''),
    ]:
        request = AnswerRequest(request_id=uuid4(), question=question, reading_context={'resource_ref': {
            'course_id': 'learning-fixture', 'material_type': 'report', 'material_id': 'a-core', 'version': material['version']}, 'selected_text': selection})
        accepted = svc.turns.accept('alice', 'learning-fixture', 'a', request)
        started = time.monotonic()
        runtime.run_once()
        result = svc.turns.get('alice', accepted['turn_id'])
        item = {'question': question, 'status': result['status'], 'error_code': result['error_code'],
                'seconds': round(time.monotonic() - started, 2), 'answer': result['result']}
        if result['status'] != 'succeeded':
            state = svc.turn_repository.get('alice', accepted['turn_id'])['checkpoint']
            item['synthetic_diagnostics'] = [m.get('content') for m in state.get('packet', {}).get('messages', []) if m['role'] == 'assistant']
        item['transport_diagnostics'] = diagnostics[:]
        diagnostics.clear()
        report['questions'].append(item)
        print(json.dumps({'question': question, 'status': result['status'], 'error_code': result['error_code'], 'seconds': item['seconds']}, ensure_ascii=False), flush=True)
finally:
    destination = Path(__file__).resolve().parents[3] / 'docs/acceptance/artifacts/learning-agent-p3-real-model.json'
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    fixture.engine.dispose()
    with fixture.admin.begin() as connection:
        connection.execute(text(f'DROP SCHEMA {fixture.schema} CASCADE'))
    fixture.admin.dispose()
if len(report['questions']) != 3 or any(q['status'] != 'succeeded' for q in report['questions']):
    raise SystemExit('One or more real-model questions failed; inspect redacted report')
