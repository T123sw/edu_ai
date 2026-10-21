import asyncio
import json
from types import SimpleNamespace
import pytest
from app.practice import service
from app.practice.pages.contracts import TeachingPlan, PROTOCOL
from app.practice.pages.generation import generate
from tests.practice.pages_fixtures import PLAN, RAW, artifact, ACTION_PLAN, TRACE, CATALOG, NARRATION

@pytest.fixture
def store(tmp_path,monkeypatch):
    monkeypatch.setenv('APP_STATE_PERSISTENCE_MODE','json')
    store=service.PracticeStore(root=tmp_path);monkeypatch.setattr(service,'PracticeStore',lambda:store)
    return store

def test_native_generation_order_and_context_and_resume(monkeypatch,store):
    calls=[]
    science={k:['相邻比较'] for k in ['core_formulas','mechanism','constraints','forbidden_errors']}
    async def complete(owner,prompt,**kw):
        calls.append(prompt)
        return json.dumps(science) if len(calls)==1 else json.dumps(ACTION_PLAN) if len(calls)==3 else json.dumps(NARRATION) if len(calls)==5 else RAW
    monkeypatch.setattr(service,'complete',complete)
    monkeypatch.setattr(service,'validate_html',lambda *args,**kw:{'ok':True,'issues':[],'trace':TRACE,'action_catalog':CATALOG})
    context=SimpleNamespace(owner_user_id='alice',task_id='pages',is_cancel_requested=lambda:False,progress=lambda *_:None)
    asyncio.run(generate({'topic':'冒泡排序'},context))
    assert len(calls)==5
    base_html=store.get('alice','pages:pages-draft')['stages']['explore']['html']
    assert base_html in calls[2] and base_html in calls[3] and base_html in calls[4]
    assert '原理演示版' in calls[3] and '自由探索HTML' in calls[4]
    result=store.get('alice','pages')
    assert result['experiment']['protocol']==PROTOCOL
    assert '演示实际执行记录' in calls[4] and 'compare-3' in calls[4]
    assert len(result['experiment']['spec']['demo_steps']) == 3
    assert result['action_evidence']['demo_trace'] == TRACE
    assert set(result['experiment']['pages'])=={'demonstrate','explore'}
    assert [s['id'] for s in result['experiment']['spec']['tasks']]==[]
    assert not store.get('bob','pages:pages-draft')
    asyncio.run(generate({'topic':'冒泡排序'},context))
    assert len(calls)==5 # Completed expensive stages are reused on retry.

def test_split_is_small_and_does_not_require_action_reference_graph():
    plan=TeachingPlan.model_validate(PLAN)
    assert len(plan.tasks)==2
    assert 'validation_cases' not in TeachingPlan.model_json_schema()['properties']

def test_complete_process_is_not_limited_by_old_step_or_task_counts():
    plan = TeachingPlan.model_validate({**PLAN, 'demo_steps': PLAN['demo_steps'] * 16,
                                       'tasks': PLAN['tasks'] * 4})
    assert len(plan.demo_steps) == 16 and len(plan.tasks) == 8

def test_assembled_page_failure_prevents_publication(monkeypatch, store):
    calls = []
    async def complete(owner, prompt, **kw):
        calls.append(prompt)
        return json.dumps({'mechanism': ['比较']}) if len(calls) == 1 else json.dumps(ACTION_PLAN) if len(calls) == 3 else json.dumps(NARRATION) if len(calls) == 5 else RAW
    checks = []
    def validate(html, **kw):
        checks.append(kw['stage_page']['phase'])
        return {'trace': TRACE, 'action_catalog': CATALOG, 'ok': len(checks) <= 2, 'issues': [] if len(checks) <= 2 else ['最终配置不可运行']}
    monkeypatch.setattr(service, 'complete', complete)
    monkeypatch.setattr(service, 'validate_html', validate)
    context = SimpleNamespace(owner_user_id='alice', task_id='failed-package', is_cancel_requested=lambda:False, progress=lambda *_:None)
    with pytest.raises(ValueError, match='拼装后'):
        asyncio.run(generate({'topic':'冒泡排序'}, context))
    assert len(calls) == 5 and len(checks) == 3
    assert not store.get('alice', 'failed-package')

def test_exploration_cannot_parse_teaching_prose_as_initial_parameters():
    from app.practice.native_runtime import wrap_native_html
    package = artifact()['experiment']
    # Reproduce the generated page's mistake: treating demo_initial as data.
    raw = RAW.replace('state={count:0};draw();',
        "if(window.__stagePage.spec.demo_initial)throw Error('教学说明污染了实验参数');state={count:0};draw();")
    html = wrap_native_html(raw, stage_page={'phase':'explore', 'spec':package['spec'], 'revision':package['revision']})
    check = service.validate_html(html, stage_page={'phase':'explore', 'spec':package['spec']})
    assert check['ok'], check

def test_continuous_task_preserves_progress_after_error_and_only_finishes_at_goal():
    from playwright.sync_api import sync_playwright
    from app.practice.native_runtime import wrap_native_html
    package = artifact()['experiment']
    raw = RAW.replace("if(phase==='guided')return{verdict:'pass'}",
                      "if(phase==='guided')return{verdict:state.count===3?'pass':'pending',feedback:'当前操作正确，请继续'}")
    html = wrap_native_html(raw, stage_page={'phase':'guided', 'spec':package['spec'], 'revision':package['revision']})
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content('<iframe sandbox="allow-scripts"></iframe>')
        page.evaluate('''html => {
          const frame=document.querySelector('iframe');
          window.onmessage=e=>{
            if(e.source!==frame.contentWindow)return;
            if(e.data.type==='edu-experiment-ready')frame.contentWindow.postMessage({type:'edu-experiment-init',nonce:'test'},'*');
            if(e.data.type==='edu-experiment-view'){window.view=e.data.view;window.busy=e.data.busy;}
          };frame.srcdoc=html;
        }''', html)
        page.wait_for_function('window.view && !window.busy')
        frame = page.frame_locator('iframe')
        def click(selector):
            seq = page.evaluate('window.view.seq')
            frame.locator(selector).click()
            page.wait_for_function('seq => window.view.seq > seq && !window.busy', arg=seq)
            return page.evaluate('window.view')
        first = click('#correct')
        assert first['index'] == 0 and first['state']['count'] == 1 and first['verdict'] == 'pending'
        failed = click('#wrong')
        assert failed['index'] == 0 and failed['state']['count'] == 1 and failed['verdict'] == 'fail'
        second = click('#correct')
        assert second['index'] == 0 and second['state']['count'] == 2 and second['feedback']
        done = click('#correct')
        assert done['index'] == 1 and done['verdict'] == 'pass'
        click('#correct'); click('#correct')
        done = click('#correct')
        assert done['index'] == 2 and done['state']['count'] == 3
        assert frame.locator('#correct').is_disabled()
        page.evaluate("document.querySelector('iframe').contentWindow.postMessage({type:'edu-experiment-intent',nonce:'test',intent:{type:'reset'}},'*')")
        page.wait_for_function('window.view.index === 1 && window.view.state.count === 0 && !window.busy')
        assert frame.locator('#correct').is_enabled()
        browser.close()

@pytest.mark.parametrize('phase',['demonstrate','guided','explore'])
def test_real_browser_page_interfaces_and_reset(phase):
    data=artifact();package=data['experiment']
    check=service.validate_html(package['pages'][phase],stage_page={'phase':phase,'spec':package['spec']})
    assert check['ok'],check

def test_missing_page_interface_is_rejected():
    from app.practice.native_runtime import wrap_native_html
    package=artifact()['experiment']
    html=wrap_native_html('<html><head></head><body>没有真实接口</body></html>',stage_page={'phase':'explore','spec':package['spec'],'revision':package['revision']})
    check=service.validate_html(html,stage_page={'phase':'explore','spec':package['spec']})
    assert not check['ok']

def test_demonstration_ignores_legacy_expected_result():
    from app.practice.native_runtime import wrap_native_html
    package = artifact()['experiment']
    package['spec']['demo_result'] = {'count':999, 'fixed':[0,1,2]}
    html = wrap_native_html(RAW, stage_page={'phase':'demonstrate','spec':package['spec'],'revision':package['revision']})
    check = service.validate_html(html, stage_page={'phase':'demonstrate','spec':package['spec']})
    assert check['ok'], check
    assert 'demo-steps-and-replay' in check['checks']

def test_guided_automatic_step_is_rejected_even_with_verdict_reporting():
    from app.practice.native_runtime import wrap_native_html
    package = artifact()['experiment']
    raw = RAW.replace('>交换</button>', '>单步</button>')
    html = wrap_native_html(raw, stage_page={'phase':'guided','spec':package['spec'],'revision':package['revision']})
    check = service.validate_html(html, stage_page={'phase':'guided','spec':package['spec']})
    assert not check['ok'] and any('替代用户判断' in issue for issue in check['issues'])

def test_guided_page_without_host_verdict_reporting_is_rejected():
    from app.practice.native_runtime import wrap_native_html
    package = artifact()['experiment']
    raw = RAW.replace('EduStage.perform', 'localOnly').replace('let state=', 'function localOnly(label,input,operation){operation()}\nlet state=')
    # A comment mentioning the API is not an actual integration.
    raw = raw.replace('function localOnly', '// EduStage.perform("pretend", {}, () => {})\nfunction localOnly')
    html = wrap_native_html(raw, stage_page={'phase':'guided','spec':package['spec'],'revision':package['revision']})
    check = service.validate_html(html, stage_page={'phase':'guided','spec':package['spec']})
    assert not check['ok'] and any('没有调用 EduStage.perform' in issue for issue in check['issues'])

@pytest.mark.parametrize('broken_restore',[False,True])
def test_random_exploration_initialization_requires_saved_state_restore(broken_restore):
    from app.practice.native_runtime import wrap_native_html
    package=artifact()['experiment']
    raw=RAW.replace('state={count:0};draw();','state={count:Math.random()};draw();')
    if broken_restore:
        raw=raw.replace('restore(s){state=s;draw()}','restore(s){draw()}')
    html=wrap_native_html(raw,stage_page={'phase':'explore','spec':package['spec'],'revision':package['revision']})
    check=service.validate_html(html,stage_page={'phase':'explore','spec':package['spec']})
    assert check['ok'] is not broken_restore,check
    if broken_restore: assert any('保存状态未正确恢复：count:' in issue for issue in check['issues'])
    else: assert 'saved-state-restore' in check['checks']

def test_cancel_stops_before_model_calls(monkeypatch,store):
    from app.services.durable_task_handlers import DurableTaskExecutionError
    async def complete(*a,**kw):raise AssertionError('Cancelled job must not call model')
    monkeypatch.setattr(service,'complete',complete)
    context=SimpleNamespace(owner_user_id='alice',task_id='cancel',is_cancel_requested=lambda:True,progress=lambda *_:None)
    with pytest.raises(DurableTaskExecutionError):asyncio.run(generate({'topic':'冒泡排序'},context))
