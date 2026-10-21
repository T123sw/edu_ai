import asyncio
import json
from types import SimpleNamespace
from app.practice import service
from app.practice.pages.narration import action_spec, bind_narration
from app.practice.native_runtime import wrap_native_html
from tests.practice.pages_fixtures import ACTION_PLAN, TRACE, CATALOG, NARRATION, ACTION_RAW


def spec():
    return bind_narration(action_spec(ACTION_PLAN, {}), TRACE, CATALOG, NARRATION)

def test_two_stage_schemas_do_not_request_tasks_or_grading():
    from app.practice.pages.narration import DemonstrationPlan, ExplorationNarration
    assert set(DemonstrationPlan.model_json_schema()['properties']) == {'title', 'objective', 'demo_initial', 'demo_actions'}
    assert set(ExplorationNarration.model_json_schema()['properties']) == {'overview', 'demo_steps', 'exploration_prompts'}


def test_narration_binds_actual_steps_by_id_not_output_order():
    result = bind_narration(action_spec(ACTION_PLAN, {}), TRACE, CATALOG,
                            {**NARRATION, 'demo_steps': list(reversed(NARRATION['demo_steps']))})
    assert [s['after'] for s in result['demo_steps']] == ['已执行第1次比较','已执行第2次比较','已执行第3次比较']
    assert result['demo_steps'][-1]['action_id'] == 'compare-3'
    missing = bind_narration(action_spec(ACTION_PLAN, {}), TRACE, CATALOG, {**NARRATION,'demo_steps':NARRATION['demo_steps'][1:]})
    assert '第2次' not in missing['demo_steps'][0]['after']


def test_browser_captures_until_actual_done_instead_of_plan_count():
    provisional = action_spec(ACTION_PLAN, {})
    assert len(provisional['demo_steps']) == 1
    html = wrap_native_html(ACTION_RAW, stage_page={'phase':'demonstrate','spec':provisional,'revision':'test'})
    result = service.validate_html(html, stage_page={'phase':'demonstrate','spec':provisional})
    assert result['ok'], result
    assert result['trace'] == TRACE


def test_browser_feedback_uses_actual_facts_and_error_preserves_progress():
    from playwright.sync_api import sync_playwright
    html = wrap_native_html(ACTION_RAW, stage_page={'phase':'guided','spec':spec(),'revision':'test'})
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content('<iframe sandbox="allow-scripts"></iframe>')
        page.evaluate('''html=>{
          const f=document.querySelector('iframe');
          window.onmessage=e=>{
            if(e.source!==f.contentWindow)return;
            if(e.data.type==='edu-experiment-ready')f.contentWindow.postMessage({type:'edu-experiment-init',nonce:'test'},'*');
            if(e.data.type==='edu-experiment-view'){window.view=e.data.view;window.busy=e.data.busy;window.error=e.data.error;}
          };f.srcdoc=html;
        }''',html)
        page.wait_for_function('window.view && !window.busy')
        def click(selector):
            seq = page.evaluate('window.view.seq')
            page.frame_locator('iframe').locator(selector).click()
            page.wait_for_function('seq=>window.view.seq>seq&&!window.busy',arg=seq)
            assert not page.evaluate('window.error')
            return page.evaluate('window.view')
        first=click('#correct')
        assert first['feedback']=='已完成 1 次，原来是 0 次。'
        failed=click('#wrong')
        assert failed['state']['count']==1 and failed['feedback']=='当前为 1 次，请重新判断。'
        second=click('#correct')
        assert second['feedback']=='已完成 2 次，原来是 1 次。'
        done=click('#correct')
        assert done['feedback']=='完成 3 次。' and done['index']==1
        action=next(e for e in second['events'] if e.get('command',{}).get('action')=='swap')
        assert action['command']['input']['facts']['count']==1
        browser.close()


def test_old_draft_keeps_sources_but_regenerates_actions_and_resumes_narration(tmp_path,monkeypatch):
    from app.practice.pages.generation import generate
    monkeypatch.setenv('APP_STATE_PERSISTENCE_MODE','json')
    store=service.PracticeStore(root=tmp_path)
    monkeypatch.setattr(service,'PracticeStore',lambda:store)
    store.put('alice','new:pages-draft',{'stages':{'science':{'raw_analysis':'science','mechanism':['比较']},'explore':{'html':ACTION_RAW},'plan':{'old':True},'demonstrate':{'html':'old'},'guided':{'html':'old'}}})
    calls=[]
    async def complete(owner,prompt,**kw):
        calls.append(prompt)
        return json.dumps(ACTION_PLAN) if len(calls)==1 else json.dumps(NARRATION) if len(calls)==3 else ACTION_RAW
    monkeypatch.setattr(service,'complete',complete)
    monkeypatch.setattr(service,'validate_html',lambda *a,**k:{'ok':True,'issues':[],'trace':TRACE,'action_catalog':CATALOG})
    ctx=SimpleNamespace(owner_user_id='alice',task_id='new',is_cancel_requested=lambda:False,progress=lambda *_:None)
    asyncio.run(generate({'topic':'冒泡排序'},ctx))
    assert len(calls)==3 and '演示实际执行记录' in calls[-1]
    artifact = store.get('alice', 'new')
    assert set(artifact['experiment']['pages']) == {'demonstrate', 'explore'}
    assert artifact['experiment']['spec']['phases'] == ['demonstrate', 'explore']
    assert artifact['experiment']['spec']['tasks'] == []
    assert '练习实际动作目录' not in calls[-1]
    draft=store.get('alice','new:pages-draft')
    del draft['stages']['narration'];store.put('alice','new:pages-draft',draft)
    async def narration_only(owner,prompt,**kw):
        assert '演示实际执行记录' in prompt
        calls.append(prompt)
        return json.dumps(NARRATION)
    monkeypatch.setattr(service,'complete',narration_only)
    asyncio.run(generate({'topic':'冒泡排序'},ctx))
    assert len(calls)==4


def test_demo_feedback_matches_action_and_replay_resets_completion():
    from playwright.sync_api import sync_playwright
    package_spec=spec()
    # A wrong binding must never display the explanation belonging to another action.
    package_spec['demo_steps'][1]['action_id']='different-action'
    html=wrap_native_html(ACTION_RAW,stage_page={'phase':'demonstrate','spec':package_spec,'revision':'test'})
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        page=browser.new_page();page.set_content('<iframe sandbox="allow-scripts"></iframe>')
        page.evaluate('''html=>{
          const f=document.querySelector('iframe');window.onmessage=e=>{
            if(e.source!==f.contentWindow)return;
            if(e.data.type==='edu-experiment-ready')f.contentWindow.postMessage({type:'edu-experiment-init',nonce:'test'},'*');
            if(e.data.type==='edu-experiment-view'){window.view=e.data.view;window.busy=e.data.busy;window.error=e.data.error;}
          };f.srcdoc=html;
        }''',html)
        page.wait_for_function('window.view&&!window.busy')
        def command(kind):
            seq=page.evaluate('window.view.seq')
            page.evaluate("type=>document.querySelector('iframe').contentWindow.postMessage({type:'edu-experiment-intent',nonce:'test',intent:{type}},'*')",kind)
            page.wait_for_function('seq=>window.view.seq>seq&&!window.busy',arg=seq)
            assert not page.evaluate('window.error')
            return page.evaluate('window.view')
        assert command('next')['feedback']=='已执行第1次比较'
        assert command('next')['feedback']=='已执行操作：compare-2'
        done=command('next')
        assert done['verdict']=='complete' and done['state']=={'count':3}
        back=command('back')
        assert back['verdict']=='' and back['state']=={'count':2} and '第2次' not in back['feedback']
        assert command('next')['feedback']=='已执行第3次比较'
        replay=command('replay')
        assert replay['state']=={'count':0} and replay['verdict']==''
        assert command('next')['feedback']=='已执行第1次比较'
        browser.close()


def test_fixed_narration_resolves_plain_fields_and_rejects_expressions_without_eval():
    from app.practice.pages.narration import trace_text
    row={'before':{'arr':[3,1],'j':0},'facts':{'swapped':False}}
    assert trace_text('数组 {{before.arr}}，首项 {{before.arr.0}}',row,'fallback')=='数组 [3, 1]，首项 3'
    assert trace_text('比较 {{before.j+1}}',row,'fallback')=='fallback'
    assert trace_text('{{before.missing}}',row,'fallback')=='fallback'
