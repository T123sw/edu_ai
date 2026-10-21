import { test } from 'node:test';
import assert from 'node:assert/strict';
// Browser probes are kept outside the frontend bundle.
// @ts-expect-error Node-only validator module
import { validatePractice } from './practice-validation.mjs';

function html(body: string, script: string) {
  return `<!doctype html><html><head><style>input{max-width:100%}</style><script>let results={count:0};window.EduPractice={report:x=>results=x,snapshot:()=>({parameters:Object.fromEntries([...document.querySelectorAll('[data-param]')].map(e=>[e.dataset.param,e.value])),results})};</script></head><body>${body}<button data-action="run">运行</button><button data-action="reset">重置</button><script>${script}</script></body></html>`;
}
const controls = '<input type="number" data-param="size" min="2" max="30" value="5"><input type="range" data-param="delay" min="100" max="5000" step="100" value="1800">';

test('a delayed sorting step is observed rather than rejected at 1.4 seconds', async () => {
  const result = await validatePractice(html(controls, `let timer;document.querySelector('[data-action="run"]').onclick=()=>{clearTimeout(timer);timer=setTimeout(()=>EduPractice.report({count:+document.querySelector('[data-param="size"]').value}),+document.querySelector('[data-param="delay"]').value)};document.querySelector('[data-action="reset"]').onclick=()=>{clearTimeout(timer);EduPractice.report({count:0})}`), { observationMs: 2500 });
  assert.equal(result.ok, true, JSON.stringify(result));
  assert.equal(result.diagnostics.trials[0].changed, true);
  assert.equal(result.diagnostics.trials[1].parameters.delay, '1800');
  assert.equal(result.diagnostics.trials[1].parameters.size, '6');
});

test('array input remains a valid array and transient reports are retained', async () => {
  const inputs = '<input data-param="array" value="3,1,2"><select data-param="pivot"><option>first</option><option>last</option></select>';
  const result = await validatePractice(html(inputs, `document.querySelector('[data-action="run"]').onclick=()=>{const a=document.querySelector('input').value.split(',').map(Number);if(a.length<2)throw Error('invalid array');EduPractice.report({count:a[0]});EduPractice.report({count:0})};document.querySelector('[data-action="reset"]').onclick=()=>EduPractice.report({count:0})`), { observationMs: 250 });
  assert.equal(result.ok, true, JSON.stringify(result));
  assert.equal(result.diagnostics.trials[1].parameters.array, '4,1,2');
  assert.equal(result.diagnostics.trials[1].changed, true);
});

test('dead pages still fail; unchanged reports do not count as interaction', async () => {
  const result = await validatePractice(html(controls, `document.querySelector('[data-action="run"]').onclick=()=>EduPractice.report({count:0});document.querySelector('[data-action="reset"]').onclick=()=>EduPractice.report({count:0})`), { observationMs: 120 });
  assert.equal(result.ok, false);
  assert.ok(result.issues.some((issue: string) => issue.includes('仍未上报结果变化')));
});

test('JavaScript failures still block delivery when another control works', async () => {
  const result = await validatePractice(html(controls, `document.querySelector('[data-action="run"]').onclick=()=>{EduPractice.report({count:Date.now()});throw Error('sorting failed')};document.querySelector('[data-action="reset"]').onclick=()=>EduPractice.report({count:0})`), { observationMs: 250 });
  assert.equal(result.ok, false);
  assert.ok(result.issues.some((issue: string) => issue.includes('sorting failed')));
});

function canvasLab(hidpi: boolean, grows = false) {
  return html(controls + '<button data-action="pause">暂停</button><canvas style="width:100%;height:260px"></canvas>', `
    const canvas=document.querySelector('canvas');let count=0,timer;
    function draw(){const dpr=${hidpi ? 'devicePixelRatio' : '1'};const w=canvas.clientWidth;
      const h=${grows ? 'Math.min(canvas.height, 1600)' : '260'};canvas.style.height=h+'px';canvas.width=w*dpr;canvas.height=h*dpr;
      const ctx=canvas.getContext('2d');ctx.setTransform(dpr,0,0,dpr,0,0);ctx.font='16px sans-serif';ctx.fillText('比较次数',20,30);}
    document.querySelector('[data-action="run"]').onclick=()=>{clearInterval(timer);EduPractice.report({count:++count});timer=setInterval(()=>EduPractice.report({count:++count}),100)};
    document.querySelector('[data-action="pause"]').onclick=()=>clearInterval(timer);
    document.querySelector('[data-action="reset"]').onclick=()=>{clearInterval(timer);count=0;EduPractice.report({count});draw()};
    window.onresize=draw;draw();
  `);
}

test('native validator accepts sharp canvas and stable repeated resizing', async () => {
  const result=await validatePractice(canvasLab(true), {native:true,observationMs:300});
  assert.equal(result.ok,true,JSON.stringify(result.issues));
  assert.equal(result.diagnostics.presentation.length,4);
  assert.equal(result.diagnostics.presentation[0].canvases[0].dpr,2);
});

test('native validator rejects the previously accepted low resolution canvas', async () => {
  const result=await validatePractice(canvasLab(false), {native:true,observationMs:300});
  assert.equal(result.ok,false);
  assert.ok(result.issues.some((issue:string)=>issue.includes('devicePixelRatio')));
});

test('native validator rejects canvas height that grows after reset and resize', async () => {
  const result=await validatePractice(canvasLab(true, true), {native:true,observationMs:300});
  assert.equal(result.ok,false);
  assert.ok(result.issues.some((issue:string)=>issue.includes('高度累积增长')));
});
