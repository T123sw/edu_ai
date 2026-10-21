import { test, expect } from 'playwright/test';
import fs from 'node:fs';

test('reference formulas initialize despite CSS-only KaTeX hints and update without re-parsing', async ({ page }) => {
  await page.setContent(String.raw`<!doctype html><html><head><style>.katex-display{margin:8px}</style></head><body>
    <details class="edu-frame-reference"><summary>原理与公式</summary>
      <section data-experiment-region="reference">
        <p id="compare">比较：\(a[i] > a[i+1]\)</p>
        <p id="fraction">次数：\[\frac{n(n-1)}{2}\]</p>
        <p id="dollars">复杂度：$$O(n^2)$$</p>
        <p id="existing"></p>
        <code id="code">\(a[i]\)</code><pre id="pre">\[n-1\]</pre>
        <input value="\(x\)"><button>运行</button>
      </section>
    </details><p id="outside">\(notReference\)</p></body></html>`);
  await page.addScriptTag({ path: 'node_modules/katex/dist/katex.min.js' });
  await page.addScriptTag({ path: 'node_modules/katex/dist/contrib/auto-render.min.js' });
  await page.evaluate(() => {
    (window as any).katex.render('x^2', document.querySelector('#existing'));
  });
  const before = await page.locator('#existing').innerHTML();
  await page.addScriptTag({ content: fs.readFileSync('src/practice/experiment/frameMath.js', 'utf8') });
  await expect(page.locator('.katex')).toHaveCount(4);
  await expect(page.locator('#fraction .mfrac')).toHaveCount(1);
  await expect(page.locator('#dollars .katex-display')).toHaveCount(1);
  await expect(page.locator('.katex-error')).toHaveCount(0);
  expect(await page.locator('#existing').innerHTML()).toBe(before);
  await page.getByText('原理与公式', { exact: true }).click();
  await expect(page.locator('#compare .katex')).toBeVisible();
  await expect(page.locator('#code')).toHaveText(String.raw`\(a[i]\)`);
  await expect(page.locator('#pre')).toHaveText(String.raw`\[n-1\]`);
  await expect(page.locator('input')).toHaveValue(String.raw`\(x\)`);
  await expect(page.locator('#outside')).toHaveText(String.raw`\(notReference\)`);
  await page.locator('#compare').evaluate(el => { el.textContent = String.raw`变化：\(n-1-i\)`; });
  await expect(page.locator('#compare .katex')).toHaveCount(1);
  await expect(page.locator('#compare annotation')).toHaveText('n-1-i');
  await page.getByText('原理与公式', { exact: true }).click();
  await page.getByText('原理与公式', { exact: true }).click();
  await expect(page.locator('.katex')).toHaveCount(4);
  await expect(page.locator('.katex .katex')).toHaveCount(0);
  expect(await page.locator('#existing').innerHTML()).toBe(before);
});
