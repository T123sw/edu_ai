import { chromium } from 'playwright';

// Drive the same sandbox/message boundary used by the application. Never accept
// a generated page's own declaration that it passed validation.
export async function validateExperiment(html, spec) {
  const issues = [], observations = [];
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
  const context = await browser.newContext({ viewport: { width: 1000, height: 800 }, deviceScaleFactor: 2 });
  const page = await context.newPage();
  page.on('pageerror', e => issues.push(e.message));
  await page.route('**/*', route => route.abort());
  async function load() {
    await page.setContent('<html><body style="margin:0"><iframe style="width:100%;height:720px;border:0" sandbox="allow-scripts"></iframe></body></html>');
    await page.evaluate(html => {
      window.experimentView = null; window.experimentError = ''; window.experimentBusy = true;
      const frame = document.querySelector('iframe');
      window.onmessage = e => {
        if (e.source !== frame.contentWindow) return;
        if (e.data?.type === 'edu-experiment-ready') frame.contentWindow.postMessage({ type: 'edu-experiment-init', nonce: 'validation' }, '*');
        if (e.data?.type === 'edu-experiment-view' && e.data.nonce === 'validation') {
          window.experimentView = e.data.view; window.experimentBusy = e.data.busy;
          if (e.data.error) window.experimentError = e.data.error;
        }
      };
      frame.srcdoc = html;
    }, html);
    await page.waitForFunction(() => window.experimentView && !window.experimentBusy, undefined, { timeout: 12000 });
  }
  async function command(intent) {
    const seq = await page.evaluate(() => window.experimentView.seq);
    await page.evaluate(intent => { window.experimentError = ''; document.querySelector('iframe').contentWindow.postMessage({ type: 'edu-experiment-intent', nonce: 'validation', intent }, '*'); }, intent);
    await page.waitForFunction(seq => window.experimentError || window.experimentView.seq > seq && !window.experimentBusy, seq, { timeout: 7000 });
    const { view, error } = await page.evaluate(() => ({ view: window.experimentView, error: window.experimentError }));
    if (error) throw Error(error);
    return view;
  }
  const applyCase = async test => {
    for (const c of test.commands) await command({ type: 'action', command: c });
    if (spec.tasks.find(t => t.id === test.task_id).submission === 'explicit_submit') await command({ type: 'submit' });
    return page.evaluate(() => window.experimentView);
  };
  try {
    await load();
    const initial = await page.evaluate(() => window.experimentView);
    for (const _step of spec.demo_steps) await command({ type: 'next' });
    const demonstrated = await page.evaluate(() => window.experimentView);
    if (JSON.stringify(initial.state) === JSON.stringify(demonstrated.state)) issues.push('演示没有产生任何状态变化');
    if (demonstrated.events.some(e => e.type === 'action' && e.actor !== 'system')) issues.push('演示动作来源错误');
    await command({ type: 'replay' });
    if (JSON.stringify((await page.evaluate(() => window.experimentView)).state) !== JSON.stringify(initial.state)) issues.push('重放没有恢复初始状态');
    for (const test of spec.validation_cases) {
      await load();
      for (const _step of spec.demo_steps) await command({ type: 'next' });
      await command({ type: 'phase', phase: 'guided' });
      for (const task of spec.tasks) {
        if (task.id === test.task_id) break;
        const prerequisite = spec.validation_cases.find(v => v.task_id === task.id && v.expected === 'pass');
        if (!prerequisite) throw Error('验收路径被尚未接入的开放评价阻断');
        const v = await applyCase(prerequisite);
        if (v.verdict !== 'pass') throw Error('前置任务正确样例未通过');
      }
      const before = await page.evaluate(() => window.experimentView);
      const after = await applyCase(test);
      const submitted = after.events.filter(e => e.type === 'attempt_submitted').at(-1);
      if (submitted?.task_id !== test.task_id || submitted?.verdict !== test.expected) throw Error(`${test.id} 判定应为 ${test.expected}，实际为 ${submitted?.verdict}`);
      if (test.expected === 'fail' && after.index !== before.index) throw Error('错误操作推进了任务');
      const task = spec.tasks.find(t => t.id === test.task_id);
      if (test.expected === 'fail' && task.recovery === 'rollback' && JSON.stringify(before.attempt_before) !== JSON.stringify(after.state)) throw Error('错误操作没有回滚');
      // Assertions are evaluated independently of the generated page adapter.
      const assertionResult = await page.evaluate(({ assertions, before, after, input }) => {
        const read = (v, path) => path.reduce((a, k) => a && Object.hasOwn(a, k) ? a[k] : undefined, v);
        const eq = (a, b) => JSON.stringify(a) === JSON.stringify(b);
        return assertions.every(c => {
          const ctx = { before, after, input }, a = read(ctx, c.path), b = c.right_path ? read(ctx, c.right_path) : c.value;
          if (a === undefined || b === undefined) return false;
          if (c.op === 'eq') return eq(a,b); if (c.op === 'ne') return !eq(a,b);
          if (c.op === 'contains') return Array.isArray(a) ? a.some(v => eq(v,b)) : typeof a === 'string' && typeof b === 'string' && a.includes(b);
          if (typeof a !== 'number' || typeof b !== 'number') return false;
          return c.op === 'near' ? Math.abs(a-b) <= c.tolerance : c.op === 'lt' ? a < b : c.op === 'lte' ? a <= b : c.op === 'gt' ? a > b : a >= b;
        });
      }, { assertions: test.assertions, before: before.attempt_before, after: after.snapshots[submitted.after], input: test.commands.at(-1).input });
      if (!assertionResult) throw Error(`${test.id} 状态断言失败`);
      observations.push({ id: test.id, verdict: submitted.verdict });
    }
    await command({ type: 'phase', phase: 'explore' });
    for (const action of spec.actions.filter(a => a.phases.includes('explore'))) await command({ type: 'action', command: { action: action.id, input: Object.fromEntries(action.parameters.map(p => [p.name, p.default])) } });
    for (const width of [1000, 360, 1000]) {
      const before = await page.evaluate(() => JSON.stringify(window.experimentView.state));
      await page.setViewportSize({ width, height: 800 });
      await page.waitForTimeout(150);
      const frame = page.frames()[1];
      const visual = await frame.evaluate(() => {
        const canvas = [...document.querySelectorAll('canvas')];
        return { overflow: document.documentElement.scrollWidth > innerWidth + 4, visible: !!document.body.innerText.trim() || canvas.length > 0 || !!document.querySelector('svg'), blurry: canvas.some(c => c.clientWidth > 20 && (c.width < c.clientWidth * devicePixelRatio - 2 || c.height < c.clientHeight * devicePixelRatio - 2)) };
      });
      if (visual.overflow || !visual.visible || visual.blurry) issues.push(`${width}px 展示检查失败：${JSON.stringify(visual)}`);
      if (before !== await page.evaluate(() => JSON.stringify(window.experimentView.state))) issues.push('缩放改变了实验状态');
    }
  } catch (e) { issues.push(e instanceof Error ? e.message : String(e)); }
  finally { await browser.close(); }
  return { ok: !issues.length, issues: [...new Set(issues)], checks: observations, evidence_kind: 'sandbox_runtime_checks', scientific_certification: false };
}
