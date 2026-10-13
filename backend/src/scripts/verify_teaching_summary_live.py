"""Opt-in summary generation with a real model and disposable learning history."""
import asyncio
import json
import os
from pathlib import Path
import time


def main():
    if os.getenv('LEARNING_LIVE_ACCEPTANCE') != '1':
        raise SystemExit('Set LEARNING_LIVE_ACCEPTANCE=1 for real model calls.')
    test_url = os.environ['LEARNING_TEST_DATABASE_URL']
    from app.services.runtime_config_resolver import runtime_config_resolver
    config = runtime_config_resolver.resolve('llm')
    os.environ['LEARNING_TEST_DATABASE_URL'] = test_url
    for flag in ('LEARNING_SESSION_V1_ENABLED', 'LEARNING_PROGRESS_V1_ENABLED', 'LEARNING_AGENT_V1_ENABLED',
                 'LEARNING_ENRICHMENT_V1_ENABLED', 'LEARNING_PREPARATION_V1_ENABLED', 'LEARNING_SCOPED_ROLLOUT', 'COURSE_PREPARATION_ENABLED'):
        os.environ[flag] = 'false'
    os.environ.update(LEARNING_BROWSER_AGENT='1', LEARNING_BROWSER_ENRICHMENT='1', LEARNING_BROWSER_PREPARATION='0', LEARNING_BROWSER_REAL='0')
    from tests.self_learning import browser_app as fixture
    from app.self_learning.model_adapter import LearningModelAdapter
    from app.chat.bounded_completion import answer_json
    from sqlalchemy import text
    svc = fixture.svc
    model = LearningModelAdapter.from_config(config)
    async def real_json(owner, system, data, seconds=25):
        result = await model.complete([{'role': 'system', 'content': system},
            {'role': 'user', 'content': json.dumps(data, ensure_ascii=False)}], [], deadline=time.monotonic() + seconds)
        return answer_json(result['content'])
    svc.checks.model_json = real_json
    output = Path(__file__).resolve().parents[3] / 'docs/acceptance/2026-10-13-teaching-continuity/summary-live.json'
    try:
        session = svc.sessions.enter('alice', 'learning-fixture', 'a')
        repo = svc.session_repository
        with repo._write(session['session_id']) as db:
            row = repo._owned(db, 'alice', session['session_id'])
            for i in range(16):
                question = '贴标签的例子对我理解变量绑定很有帮助。' if i == 1 else '我仍不理解可变对象的原地修改和重新赋值有什么区别。' if i == 2 else f'复习变量绑定第{i}个例子。'
                repo._append(db, row, f'summary-u-{i}', 'user', question, 'user_content', {'request_id': f'summary-{i}'})
                repo._append(db, row, f'summary-a-{i}', 'assistant', '赋值改变变量名绑定的对象，原地修改则改变对象本身。', 'assistant_content', {'request_id': f'summary-{i}'})
        assert asyncio.run(svc.summaries.summarize('alice', session['session_id']))
        summary = svc.summaries.read('alice', session['session_id'])
        assert any(i['category'] == 'helpful_explanation' and 'summary-u-1' in i['source_ids'] for i in summary['items'])
        assert any(i['category'] in ('difficulty', 'open_question') and 'summary-u-2' in i['source_ids'] for i in summary['items'])
        output.write_text(json.dumps({'model': config['model'], 'summary': summary, 'status': 'passed'}, ensure_ascii=False, indent=2))
    finally:
        fixture.engine.dispose()
        with fixture.admin.begin() as db:
            db.execute(text(f'DROP SCHEMA {fixture.schema} CASCADE'))
        fixture.admin.dispose()


if __name__ == '__main__':
    main()
