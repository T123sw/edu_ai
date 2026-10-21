import { chromium } from 'playwright';

// Probe real interactions using valid defaults first. Controls are changed one at
// a time: the largest value may be the slowest animation, or an invalid dataset.
export async function validatePractice(html, { observationMs = 8000, native = false } = {}) {
  const browser = await chromium.launch({ headless: true });
  const issues = [], errors = [], trials = [];
  let controls = [], initial;
  const presentation = [];
  const bounded = value => {
    const text = JSON.stringify(value ?? null);
    if (text.length > 14000) throw new Error('实验上报状态超过大小限制');
    return JSON.parse(text);
  };
  try {
    const page = await browser.newPage({ viewport: { width: native ? 1440 : 1150, height: 900 }, deviceScaleFactor: native ? 2 : 1 });
    if (native) await page.addInitScript(() => {
      window.__practiceTextDraws = new Map();
      const fillText = CanvasRenderingContext2D.prototype.fillText;
      CanvasRenderingContext2D.prototype.fillText = function (...args) {
        const font = parseFloat(this.font.match(/([\d.]+)px/)?.[1]);
        const transform = this.getTransform();
        const size = font * Math.hypot(transform.a, transform.b);
        const previous = window.__practiceTextDraws.get(this.canvas);
        if (size > 0) window.__practiceTextDraws.set(this.canvas, Math.min(previous ?? Infinity, size));
        return fillText.apply(this, args);
      };
    });
    page.setDefaultTimeout(3000);
    await page.route('**/*', route => route.abort());
    page.on('pageerror', error => errors.push(error.message));
    await page.setContent('<iframe sandbox="allow-scripts" style="width:100%;height:750px;border:0"></iframe>');
    await page.locator('iframe').evaluate((element, source) => { element.srcdoc = source; }, html);
    const frame = page.frameLocator('iframe');
    await frame.locator('body').waitFor();
    const target = page.frames().find(item => item !== page.mainFrame());
    try {
      await target.waitForFunction(() => window.EduPractice && Object.keys(window.EduPractice.snapshot().results || {}).length > 0);
    } catch {
      throw new Error('初始化后没有上报结果。请在初始化结束直接调用 EduPractice.report(实际初始结果)，不要用 lastReport/performance.now 节流丢弃首次或末次更新；宿主已负责合并消息。');
    }
    const snapshot = async () => bounded(await target.evaluate(() => window.EduPractice.snapshot()));
    const inspectPresentation = async label => {
      await page.waitForTimeout(250);
      const result = await target.evaluate(() => ({
        width: innerWidth,
        height: document.body.scrollHeight,
        overflow: document.documentElement.scrollWidth > innerWidth + 4,
        canvases: [...document.querySelectorAll('canvas')].map(canvas => {
          const box = canvas.getBoundingClientRect();
          const draw = window.__practiceTextDraws?.get(canvas);
          return { id: canvas.id, width: canvas.width, height: canvas.height, cssWidth: box.width, cssHeight: box.height,
            fontSize: draw && draw * box.width / canvas.width, dpr: devicePixelRatio };
        }).filter(item => item.cssWidth > 0 && item.cssHeight > 0),
      }));
      presentation.push({ label, ...result });
      if (result.overflow) issues.push(`${label}实验内容横向溢出`);
      for (const canvas of result.canvases) {
        if (canvas.width + 2 < canvas.cssWidth * canvas.dpr || canvas.height + 2 < canvas.cssHeight * canvas.dpr)
          issues.push(`${label}画布 ${canvas.id} 未按 devicePixelRatio 设置高清位图尺寸`);
        if (canvas.fontSize && canvas.fontSize < 12.5)
          issues.push(`${label}画布 ${canvas.id} 字号仅 ${canvas.fontSize.toFixed(1)}px，请至少13px`);
      }
      return result;
    };
    const initialPresentation = native ? await inspectPresentation('桌面高清屏') : null;
    initial = await snapshot();
    const params = frame.locator('input[data-param],select[data-param],textarea[data-param]');
    controls = await params.evaluateAll(elements => elements.map(element => ({
      name: element.dataset.param, type: element.tagName === 'SELECT' ? 'select' : element.type,
      min: element.min, max: element.max, step: element.step, value: element.value,
    })));
    if (controls.length < 2) issues.push('缺少两个可操作参数');
    // Capture reports at the time they occur, including short intermediate steps
    // that could be missed by comparing only the initial and final snapshots.
    await target.evaluate(() => {
      const report = window.EduPractice.report.bind(window.EduPractice);
      window.__practiceProbe = { baseline: '', changed: false };
      window.EduPractice.report = value => {
        report(value);
        const probe = window.__practiceProbe;
        if (JSON.stringify(window.EduPractice.snapshot().results) !== probe.baseline) probe.changed = true;
      };
    });
    const arm = () => target.evaluate(() => {
      window.__practiceProbe = { baseline: JSON.stringify(window.EduPractice.snapshot().results), changed: false };
    });
    const observe = async () => {
      try { await target.waitForFunction(() => window.__practiceProbe.changed, null, { timeout: observationMs, polling: 100 }); return true; }
      catch (error) { if (error.name !== 'TimeoutError') throw error; return false; }
    };
    await arm();
    await frame.locator('[data-action="run"]').click();
    const defaultChanged = await observe();
    if (native && !defaultChanged) issues.push('默认参数点击运行后，观察窗口内仍未上报结果变化');
    trials.push({ action: 'run-with-defaults', before: initial, after: await snapshot(), changed: defaultChanged });
    await frame.locator('[data-action="reset"]').click();
    await page.waitForTimeout(200);
    if (native) {
      const pause = frame.locator('[data-action="pause"]');
      if (!await pause.count()) issues.push('原生实验缺少暂停按钮 data-action="pause"');
      else {
        await frame.locator('[data-action="run"]').click();
        await page.waitForTimeout(250);
        await pause.click();
        await page.waitForTimeout(200);
        const paused = JSON.stringify((await snapshot()).results);
        await page.waitForTimeout(400);
        if (paused !== JSON.stringify((await snapshot()).results)) issues.push('点击暂停后实验结果仍持续变化');
        await frame.locator('[data-action="reset"]').click();
      }
    }
    let parameterChanged = false;
    // A maximum of three independent probes keeps the total check bounded.
    for (let index = 0; index < Math.min(controls.length, 3); index++) {
      const before = await snapshot();
      await arm();
      const changedControl = await params.nth(index).evaluate(element => {
        const old = element.value;
        if (element.disabled || element.readOnly) return false;
        if (element.tagName === 'SELECT') {
          const next = [...element.options].findIndex(option => !option.disabled && option.value !== old);
          if (next < 0) return false;
          element.selectedIndex = next;
        } else if (element.type === 'checkbox') element.checked = !element.checked;
        else if (['range', 'number'].includes(element.type)) {
          const value = Number(old), step = element.step && element.step !== 'any' ? Number(element.step) : 1;
          const min = element.min !== '' ? Number(element.min) : value - step * 10;
          const max = element.max !== '' ? Number(element.max) : value + step * 10;
          // Stay close to the default, away from slow/degenerate extremes.
          const next = value + step <= max ? value + step : value - step >= min ? value - step : value;
          element.value = String(Number(next.toPrecision(12)));
          if (!element.checkValidity() || element.value === old) { element.value = old; return false; }
        } else if (/^\s*-?\d+(\s*,\s*-?\d+){1,}\s*$/.test(old)) {
          const array = old.split(',').map(Number); array[0] += 1; element.value = array.join(',');
          if (!element.checkValidity()) { element.value = old; return false; }
        } else return false; // Never turn arbitrary text into the number 100.
        element.dispatchEvent(new Event('input', { bubbles: true }));
        element.dispatchEvent(new Event('change', { bubbles: true }));
        return true;
      });
      if (!changedControl) { trials.push({ action: 'skip-unsupported-control', control: controls[index].name }); continue; }
      const changedParameters = (await snapshot()).parameters;
      await frame.locator('[data-action="run"]').click();
      const changed = await observe();
      trials.push({ action: 'change-one-parameter-and-run', control: controls[index].name, parameters: changedParameters, before, after: await snapshot(), changed });
      await frame.locator('[data-action="reset"]').click();
      await page.waitForTimeout(200);
      if (changed) { parameterChanged = true; break; }
    }
    // Still fail dead pages; do not bypass the result-change check.
    if (!parameterChanged) issues.push('逐项调整有效参数并运行后，观察窗口内仍未上报结果变化');
    if (await target.evaluate(() => document.body.scrollWidth > innerWidth + 4)) issues.push('实验页面横向溢出');
    await page.setViewportSize({ width: 390, height: 850 });
    await page.waitForTimeout(200);
    if (await target.evaluate(() => document.body.scrollWidth > innerWidth + 4)) issues.push('实验页面在窄屏横向溢出');
    if (native) {
      await inspectPresentation('手机高清屏');
      await page.setViewportSize({ width: 1100, height: 900 });
      await inspectPresentation('窄桌面高清屏');
      await page.setViewportSize({ width: 1440, height: 900 });
      await frame.locator('[data-action="reset"]').click();
      const restored = await inspectPresentation('恢复桌面宽度');
      if (initialPresentation && restored.canvases.some((canvas, index) => {
        const before = initialPresentation.canvases[index];
        return before && canvas.cssHeight > before.cssHeight * 1.2 + 4;
      })) issues.push('恢复相同宽度后画布高度累积增长，请分离逻辑尺寸与位图尺寸');
    }
  } catch (error) { issues.push(String(error.message).slice(0, 700)); }
  finally { await browser.close(); }
  issues.push(...errors.slice(0, 5));
  return { ok: issues.length === 0, issues: [...new Set(issues)], checks: ['initial-results', 'default-run', 'valid-parameter-change-and-run', 'reset-button', 'responsive-layout', 'javascript-errors', ...(native ? ['hidpi-canvas', 'canvas-label-size', 'resize-stability', 'pause-button'] : [])], scope: 'browser-smoke-not-scientific-certification', diagnostics: { observation_ms: observationMs, controls, initial, trials, presentation } };
}
