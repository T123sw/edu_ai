import { chromium } from 'playwright';
import { isDeepStrictEqual } from 'node:util';
import { parse } from 'acorn';

function hasGuidedReporting(scripts) {
  const member = (node, name) => node?.type === 'MemberExpression' &&
    (node.computed ? node.property.value === name : node.property.name === name);
  const visit = node => {
    if (!node || typeof node !== 'object') return false;
    if (node.type === 'CallExpression' && member(node.callee, 'perform')) {
      const object = node.callee.object;
      if (object?.name === 'EduStage' || member(object, 'EduStage')) return true;
    }
    return Object.values(node).some(value => Array.isArray(value) ? value.some(visit) : visit(value));
  };
  return scripts.some(source => {
    if (!source.includes('perform')) return false;
    try { return visit(parse(source, {ecmaVersion: 'latest', sourceType: 'module'})); }
    catch { return false; } // Syntax errors are also captured by the browser.
  });
}

// Basic integration check only: no model reviewer or generated answer suite.
export async function validateStagePage(html, {phase, spec}) {
  const issues = [], checks = [], trace = [];
  let action_catalog = [];
  const browser = await chromium.launch({headless: true, args: ['--no-sandbox']});
  try {
    const page = await browser.newPage({viewport: {width: 1100, height: 800}});
    page.on('pageerror', e => issues.push(e.message));
    await page.route('**/*', route => route.abort());
    await page.setContent('<iframe sandbox="allow-scripts" style="width:100%;height:720px"></iframe>');
    const mount = async saved => page.evaluate(({html, saved}) => {
      window.stageView = null; window.stageBusy = true; window.stageError = '';
      const frame = document.querySelector('iframe');
      window.onmessage = e => {
        if(e.source !== frame.contentWindow) return;
        if(e.data?.type === 'edu-experiment-ready') frame.contentWindow.postMessage({type:'edu-experiment-init',nonce:'check',view:saved},'*');
        if(e.data?.type === 'edu-experiment-view' && e.data.nonce === 'check') {
          window.stageView=e.data.view; window.stageBusy=e.data.busy;
          if(e.data.error) window.stageError=e.data.error;
        }
      };
      frame.srcdoc=html;
    },{html, saved});
    await mount();
    const settled = async () => {
      await page.waitForFunction(() => window.stageError || window.stageView && !window.stageBusy,undefined,{timeout:15000});
      const error=await page.evaluate(()=>window.stageError); if(error) throw Error(error);
    };
    await settled(); checks.push('registered-and-initialized');
    if (phase === 'guided') {
      const scripts = await page.frames()[1].locator('script:not([src])').allTextContents();
      if (!hasGuidedReporting(scripts)) throw Error('练习页没有调用 EduStage.perform：请将真实状态修改放进其回调，每次操作返回 pending/pass/fail 和 feedback；初始化和异步操作必须等待完成，不能只在页面内部处理按钮。');
      if (await page.frames()[1].getByRole('button', {name:/^(单步|下一步|自动完成)$/}).count()) throw Error('动手实践不能用单步/下一步/自动完成替代用户判断。请提供实际选择或操作（例如交换/不交换），根据选择判对错，正确中间操作pending，完成全过程才pass。');
      checks.push('guided-reporting-connected');
      if (spec.action_protocol) {
        action_catalog = await page.frames()[1].evaluate(() => window.EduStage.describeActions());
        if (!action_catalog.length || action_catalog.some(a => !a.id || !a.label || !a.rule)) throw Error('练习页请注册 actions: [{id,label,rule,facts}]，描述真实操作及判定分支，供后续生成讲解。');
      }
    }
    const initial=await page.evaluate(()=>window.stageView);
    const command=async intent=>{
      const seq=await page.evaluate(()=>window.stageView.seq);
      await page.evaluate(intent=>document.querySelector('iframe').contentWindow.postMessage({type:'edu-experiment-intent',nonce:'check',intent},'*'),intent);
      await page.waitForFunction(seq=>window.stageError || window.stageView.seq>seq && !window.stageBusy,seq,{timeout:15000});
      await settled();
    };
    if(phase==='demonstrate') {
      if (spec.action_protocol) {
        // Capture executed transitions, not a model-predicted number of steps.
        for (let i = 0; i < 256; i++) {
          const before = await page.evaluate(() => window.stageView.state);
          await command({type:'next'});
          const view = await page.evaluate(() => window.stageView);
          trace.push({id:`demo-${i+1}`, ...view.last_input, before, after:view.state});
          if (view.last_input.done) break;
        }
        if (!trace.at(-1)?.done) throw Error('演示执行未结束：请采用简短的确定性初始案例，并在真实结束时返回 done:true。');
      } else for(const _ of spec.demo_steps) await command({type:'next'});
      // Exercise the interface without treating model-predicted state as an oracle.
      // Older plans may still contain demo_result; it is not a publish gate.
      await command({type:'replay'}); checks.push('demo-steps-and-replay');
    } else await command({type:'reset'});
    const restored=await page.evaluate(()=>window.stageView.state);
    // Teaching scenarios must replay their specified starting conditions.
    // Exploration may initialize a fresh random sample; test persisted restore
    // through a fresh iframe below instead of requiring random samples to match.
    if(phase!=='explore' && !isDeepStrictEqual(restored,initial.state)) throw Error('重置未恢复初始状态');
    checks.push('reset');
    await mount(initial);
    await settled();
    const resumed=await page.evaluate(()=>window.stageView.state);
    if(!isDeepStrictEqual(resumed,initial.state)) {
      const keys=[...new Set([...Object.keys(initial.state),...Object.keys(resumed)])];
      const changes=keys.filter(key=>!isDeepStrictEqual(resumed[key],initial.state[key])).slice(0,6)
        .map(key=>`${key}: 期望 ${JSON.stringify(initial.state[key])?.slice(0,120)}，实际 ${JSON.stringify(resumed[key])?.slice(0,120)}`);
      throw Error('保存状态未正确恢复：'+changes.join('；'));
    }
    checks.push('saved-state-restore');
    const frame=page.frames()[1];
    if(!await frame.locator('body').evaluate(el=>!!el.innerText.trim() || !!el.querySelector('canvas,svg'))) throw Error('实验展示为空');
    checks.push('visible-content');
  } catch(e) { issues.push(e instanceof Error ? e.message : String(e)); }
  finally { await browser.close(); }
  return {ok:!issues.length,issues,checks,trace,action_catalog,scope:'basic-page-runtime',scientific_certification:false};
}
