"""Run against a temporary Vite .classroom-e/ harness; never calls backend/models."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

OUT = Path(__file__).resolve().parent
URL = 'http://127.0.0.1:5189/.classroom-e/index.html'
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    results = []
    for name, width, height in [('desktop', 1440, 1000), ('narrow', 390, 844)]:
        context = browser.new_context(viewport={'width': width, 'height': height}, locale='zh-CN')
        context.tracing.start(screenshots=True, snapshots=True, sources=True)
        page = context.new_page(); errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(URL)
        expect(page.get_by_role('button', name='追踪一次加法')).to_be_visible(timeout=60000)
        expect(page.locator('svg')).not_to_have_count(0)
        page.screenshot(path=str(OUT / f'{name}-flow.png'), full_page=True)
        # Actual browser timers and reading-dwell playback, without pretending
        # headless speech synthesis or fabricated audio callbacks are heard audio.
        page.evaluate('delete window.speechSynthesis')
        page.locator('#play').click()
        expect(page.locator('#narration')).not_to_have_text('', timeout=10000)
        expect(page.locator('#complete')).to_have_text('1', timeout=60000)
        page.get_by_role('button', name='职责分工', exact=True).click()
        expect(page.get_by_text('模型选择工具', exact=True)).to_be_visible()
        page.screenshot(path=str(OUT / f'{name}-principle.png'), full_page=True)
        page.get_by_role('button', name='检查理解', exact=True).click()
        expect(page.get_by_text('正确答案：B', exact=True)).to_have_count(0)
        page.screenshot(path=str(OUT / f'{name}-question.png'), full_page=True)
        page.get_by_role('radio').last.check()
        page.get_by_role('button', name='提交并查看解析').click()
        expect(page.get_by_text('回答正确', exact=True)).to_be_visible()
        expect(page.get_by_text('正确答案：B', exact=True)).to_be_visible()
        page.screenshot(path=str(OUT / f'{name}-feedback.png'), full_page=True)
        page.reload()
        page.get_by_role('button', name='检查理解', exact=True).click()
        expect(page.get_by_text('正确答案：B', exact=True)).to_be_visible()
        page.get_by_role('button', name='重新作答').click()
        expect(page.get_by_text('正确答案：B', exact=True)).to_have_count(0)
        assert not errors, errors
        context.tracing.stop(path=str(OUT / f'{name}-trace.zip'))
        results.append({'viewport': name, 'passed': True, 'page_errors': errors,
                        'playback': 'reading_dwell_completed', 'audio_listening': 'not_tested',
                        'scope': 'deterministic fixture with actual native React components; no backend'})
        context.close()
    browser.close()
(OUT / 'component-results.json').write_text(json.dumps(results, ensure_ascii=False, indent=2)+'\n')
print(json.dumps(results, ensure_ascii=False))
