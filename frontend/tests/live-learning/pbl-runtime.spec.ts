import { test, expect } from 'playwright/test';
test('循环可停止，停止后正确实现能再次运行', async ({ page }) => {
  page.on('console',m=>console.log('browser',m.type(),m.text().slice(0,400)));
  page.on('pageerror',e=>console.log('error',e.message));
  page.on('requestfailed',r=>console.log('requestfailed',r.url(),r.failure()));
  await page.goto('/pbl-probe.html');
  await expect(page.getByTestId('runtime-ready')).toHaveText('ready');
  console.log('frames',page.frames().map(f=>f.url()));
  await page.getByRole('button', { name: '加载死循环样例' }).click();
  await page.getByRole('button', { name: '运行样例',exact:true }).click();
  await expect(page.getByTestId('run-status')).toHaveText('running');
  await page.getByRole('button', { name: '停止',exact:true }).click();
  await expect(page.getByTestId('run-status')).toHaveText('canceled');
  await page.getByRole('button', { name: '加载正确样例' }).click();
  await page.getByRole('button', { name: '检查练习',exact:true }).click();
  await expect(page.getByTestId('run-status')).toHaveText('passed');
  await expect(page.getByTestId('case-count')).toHaveText('9');
});

test('真实 Worker 错误、超时与资源清理', async ({page}) => {
  await page.goto('/pbl-probe.html');
  await expect(page.getByTestId('runtime-ready')).toHaveText('ready');
  const runtime = page.frames().find(frame=>frame.url().startsWith('https://2-19-8-sandpack.codesandbox.io/'))!;
  await runtime.evaluate(() => {
    const urls = new Set<string>();
    const create = URL.createObjectURL.bind(URL), revoke = URL.revokeObjectURL.bind(URL);
    URL.createObjectURL = object => { const url=create(object); urls.add(url); return url; };
    URL.revokeObjectURL = url => {urls.delete(url); revoke(url);};
    Object.assign(window,{pblLiveURLs:urls});
  });
  for (const [code, error] of [
    ["export function quickSort(a) { throw new Error('NOT_IMPLEMENTED'); }", 'NOT_IMPLEMENTED'],
    ['export function quickSort( {', 'SYNTAX_ERROR'],
    ['export const other = 1;', 'EXPORT_MISSING'],
    ['export function quickSort(a) { return quickSort(a); }', 'RUNTIME_ERROR'],
    ['export function quickSort(a) { while(true) {} }', 'TIMEOUT'],
    ['while(true) {} export function quickSort(a) { return a; }', 'TIMEOUT'],
    ['export function quickSort(a) { return new Array(a.length); }', 'INVALID_RESULT'],
    ['export function quickSort(a) { return [undefined,1,2,3]; }', 'INVALID_RESULT'],
    ['export function quickSort(a) { return [NaN,1,2,3]; }', 'INVALID_RESULT'],
    ['export function quickSort(a) { return ()=>1; }', 'INVALID_RESULT'],
    ['export function quickSort(a) { return new Array(1000000).fill(1); }', 'INVALID_RESULT'],
    ['export function quickSort(a) { return a.sort((a,b)=>a-b); }', 'INPUT_MUTATED'],
    ['export function quickSort(a) { delete a[0]; return [1,2,3,4]; }', 'INPUT_MUTATED'],
    ['export function quickSort(a) { return a; }', 'RETURNED_INPUT'],
    ['export function quickSort(a) { return [1,2,3]; }', 'OUTPUT_MISMATCH'],
    ['export function quickSort(a) { postMessage({passed:true}); return []; }', 'OUTPUT_MISMATCH'],
  ]) {
    await page.getByLabel('原型源码').fill(code);
    await page.getByRole('button',{name:'运行样例',exact:true}).click();
    await expect(page.getByTestId('run-error')).toHaveText(error);
    expect(await runtime.evaluate(()=> (window as unknown as {pblLiveURLs:Set<string>}).pblLiveURLs.size)).toBe(0);
  }
  await page.getByRole('button',{name:'加载正确样例'}).click();
  await page.getByRole('button',{name:'检查练习',exact:true}).click();
  await expect(page.getByTestId('run-status')).toHaveText('passed');
});
