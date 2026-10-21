import {expect,type Page} from 'playwright/test';
export async function enterWorkbench(page:Page) {
  const stage=page.locator('.pbl-workbench-stage');await stage.waitFor();
  // Let a preceding return scroll commit before deciding whether entry is needed.
  await page.evaluate(()=>new Promise<void>(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve()))));
  if(Math.abs((await stage.boundingBox())!.y)>2){
    // Scrolling into the workspace can activate it and remove its entry overlay.
    // Let that transition settle before deciding whether a click is still needed.
    await stage.scrollIntoViewIfNeeded();
    await page.evaluate(()=>new Promise<void>(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve()))));
    if(await stage.getAttribute('data-focused')!=='true')
      await page.getByRole('button',{name:/^(打开|展开)工作区$/}).click();
  }
  await expect(stage).toHaveAttribute('data-focused','true');
}
