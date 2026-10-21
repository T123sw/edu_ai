import { chromium } from 'playwright';

export async function validateGuidance(html, manifest) {
  const browser = await chromium.launch(); const issues = [], events = [];
  try {
    const page = await browser.newPage({ viewport: { width: 1100, height: 950 }, deviceScaleFactor: 2 });
    await page.addInitScript(() => {
      window.__guidanceDrawing = new Map();
      const proto = CanvasRenderingContext2D.prototype, clear = proto.clearRect, fillText = proto.fillText;
      proto.clearRect = function(...args) { window.__guidanceDrawing.set(this.canvas, []); return clear.apply(this,args); };
      proto.fillText = function(text,x,y,...rest) {
        const box=this.measureText(text),transform=this.getTransform(),scale=this.canvas.clientWidth/this.canvas.width;
        let left=x; if(this.textAlign==='center')left-=box.width/2;else if(['right','end'].includes(this.textAlign))left-=box.width;
        const px=transform.a*left+transform.e,py=transform.d*y+transform.f;
        const list=window.__guidanceDrawing.get(this.canvas)||[];
        if(px < -3 || px+box.width*transform.a > this.canvas.width+3 || py < -3 || py > this.canvas.height+3)list.push('文字超出画布边界：'+text);
        const font=Number(this.font.match(/([\d.]+)px/)?.[1]); if(font*transform.a*scale<12.5)list.push('画布字号小于13px：'+text);
        window.__guidanceDrawing.set(this.canvas,list);return fillText.call(this,text,x,y,...rest);
      };
      for(const method of ['moveTo','lineTo']){const original=proto[method];proto[method]=function(x,y){const t=this.getTransform(),px=t.a*x+t.c*y+t.e,py=t.b*x+t.d*y+t.f;const list=window.__guidanceDrawing.get(this.canvas)||[];if(px < -4 || px > this.canvas.width+4 || py < -4 || py > this.canvas.height+4)list.push('图形路径超出画布边界');window.__guidanceDrawing.set(this.canvas,list);return original.call(this,x,y);};}
    });
    page.on('pageerror', e => issues.push(e.message));
    await page.route('**/*', route => route.abort());
    await page.setContent('<iframe sandbox="allow-scripts" style="width:100%;height:900px;border:0"></iframe>');
    await page.evaluate(({ html, revision }) => {
      window.messages = [];
      window.addEventListener('message', event => {
        if (event.source !== document.querySelector('iframe').contentWindow) return;
        window.messages.push(event.data);
        if (event.data.type === 'edu-guidance-ready') event.source.postMessage({ type: 'edu-guidance-init', channel: 'validation', revision }, '*');
      });
      document.querySelector('iframe').srcdoc = html;
    }, { html, revision: manifest.revision });
    await page.waitForFunction(() => window.messages.some(m => m.type === 'edu-guidance-initialized'), null, { timeout: 5000 });
    const target = page.frames()[1], frame = page.frameLocator('iframe');
    const state = () => target.evaluate(() => window.EduGuidance.inspect());
    const click = async action => { await frame.locator(`[data-guidance-action="${action}"]`).first().click(); };
    const invoke = async (action, value) => target.evaluate(({ action, value }) => window.EduGuidance.dispatch(action, value), { action, value });
    const initial = await state();
    await invoke('array', [9,2,1]);
    if ((await state()).feedback.outcome !== 'blocked') issues.push('引导阶段允许越权更改数组');
    const readDrawing = async () => target.evaluate(() => [...(window.__guidanceDrawing?.values() || [])].flat());
    issues.push(...await readDrawing());
    const before = await frame.locator('canvas').first().evaluate(canvas => canvas.toDataURL());
    if (manifest.kind === 'quicksort') {
      await click('select'); await click('confirm'); await click('enter');
      let current = await state();
      const m = current.attempts[current.active].model;
      const wrong = m.array[m.scan] <= m.pivot ? 'right' : 'left';
      const original = JSON.stringify(m);
      await click(wrong); current = await state();
      if (current.feedback.outcome !== 'incorrect' || JSON.stringify(current.attempts[current.active].model) !== original) issues.push('错误判断改变模型或缺少纠错反馈');
      for (let i=0;i<40;i++) {
        current=await state(); const a=current.attempts[current.active]; if(a.complete)break;
        const model=a.model; await click(model.phase==='scan'?(model.array[model.scan]<=model.pivot?'left':'right'):'advance');
      }
      await click('enter');
    } else {
      await invoke('run'); await invoke('pause');
    }
    for (let i=0;i<250;i++) {
      const current=await state(),a=current.attempts[current.active];
      if(a.complete) {
        const index=manifest.steps.findIndex(s=>s.id===current.active);
        if(index===manifest.steps.length-1)break;
        await click('enter'); await invoke(index===0?'mu':'velocity',index===0?.6:8);
      } else await invoke('advance');
    }
    const end=await state();
    if (!manifest.steps.every(step=>end.attempts[step.id]?.complete)) issues.push('无法完成全部教学步骤');
    const after=await frame.locator('canvas').first().evaluate(canvas=>canvas.toDataURL());
    if(before===after)issues.push('操作后画布没有可见变化');
    await invoke('enter','explore');
    const explore=await state();
    if(explore.active!=='explore')issues.push('无法进入完整实验');
    await invoke('retry');
    if(manifest.kind==='quicksort') { await invoke('array',[3,-1,3,0]); for(let i=0;i<70;i++)await invoke('advance'); const m=(await state()).attempts.explore.model;if(JSON.stringify(m.array)!=='[-1,0,3,3]')issues.push('自由探索排序不正确'); }
    for(const width of [1440,1100,390]) {
      await page.setViewportSize({width,height:950}); await page.waitForTimeout(100);
      issues.push(...await readDrawing());
      const view=await target.evaluate(()=>({overflow:document.documentElement.scrollWidth>innerWidth+3,canvases:[...document.querySelectorAll('canvas')].map(c=>({width:c.width,height:c.height,w:c.getBoundingClientRect().width,h:c.getBoundingClientRect().height,dpr:devicePixelRatio}))}));
      if(view.overflow)issues.push(`${width}px 横向溢出`);
      if(view.canvases.some(c=>c.h<559))issues.push(`${width}px 展示画布不足560px`);
      if(view.canvases.some(c=>c.width+2<c.w*c.dpr||c.height+2<c.h*c.dpr))issues.push(`${width}px 画布不清晰`);
    }
    const messages=await page.evaluate(()=>window.messages);
    events.push(...messages.filter(m=>m.type==='edu-guidance-event').map(m=>({command:m.command,feedback:m.state.feedback})));
    issues.push(...messages.filter(m=>m.type==='edu-guidance-error').map(m=>m.message));
    if(events.some(event=>!event.feedback.summary))issues.push('操作缺少反馈');
    return {ok:issues.length===0,issues:[...new Set(issues)],checks:['step-permissions','incorrect-feedback','all-steps','free-exploration','canvas-change','hidpi','responsive'],scope:'guided-domain-contract',diagnostics:{initial,events}};
  } catch(error) {return {ok:false,issues:[...issues,String(error.message)],scope:'guided-domain-contract'};}
  finally {await browser.close();}
}
