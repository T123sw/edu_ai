import { test, expect } from 'playwright/test';
test('quiz material uses durable check attempts and restores after refresh', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('edu-ai-auth', JSON.stringify({ token:'alice', user:{ username:'alice', role:'student' } })));
  await page.goto('/#/classroom/learning-fixture?resource=a-quiz');
  const frame=page.frameLocator('iframe.sl-live-material');
  await expect(frame.getByText('执行 x = 1 后 x 是多少？',{exact:true})).toBeVisible();
  await frame.getByLabel('整数 1',{exact:true}).check();
  await frame.getByRole('button',{name:'提交检查答案',exact:true}).click();
  await expect(frame.getByText('客观批改 · 本题正确',{exact:true})).toBeVisible();
  await page.reload();
  await expect(frame.getByText('客观批改 · 本题正确',{exact:true})).toBeVisible();
  await expect(page.getByRole('button',{name:'继续学习',exact:true})).toBeEnabled();
});

test('actual classroom iframe reports versioned scene and restores it',async({page})=>{
  await page.addInitScript(() => localStorage.setItem('edu-ai-auth', JSON.stringify({ token:'alice', user:{ username:'alice', role:'student' } })));
  await page.goto('/#/classroom/learning-fixture?resource=b-classroom');
  const frame=page.frameLocator('iframe.sl-live-material');
  await expect(frame.getByRole('region',{name:'课堂舞台'})).toBeVisible();
  const next=frame.getByRole('button',{name:'下一页'});
  if(await next.isEnabled()) await next.click();
  await expect(frame.getByRole('button',{name:'上一页'})).toBeEnabled();
  await expect.poll(async()=>page.evaluate(async()=>{
    const response=await fetch('http://127.0.0.1:8016/api/self-learning/courses/learning-fixture/progress',{headers:{Authorization:'Bearer alice'}});
    const value=await response.json();
    return value.resources?.find((r:{resource_ref:{material_id:string}})=>r.resource_ref.material_id==='b-classroom')?.locator?.scene_id;
  })).toBe('scene-2');
  await page.reload();
  await expect(frame.getByRole('button',{name:'上一页'})).toBeEnabled();
});
