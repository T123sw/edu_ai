import { test, expect } from 'playwright/test';
import { writeFileSync } from 'node:fs';
test('real model: conversation, guided hint, check, saved quiz, document and personal revision', async ({ page, request }) => {
  const log: Record<string,unknown>[]=[];
  const headers={Authorization:'Bearer alice'};
  const api='http://127.0.0.1:8016/api/self-learning';
  await page.addInitScript(() => localStorage.setItem('edu-ai-auth', JSON.stringify({ token:'alice', user:{ username:'alice', role:'student' } })));
  await page.goto('/#/classroom/learning-fixture?resource=a-core');
  const asked = new Set<string>();
  async function ask(question:string) {
    const start=Date.now();
    await page.getByRole('textbox',{name:'向学习 Agent 提问'}).fill(question);
    await page.getByRole('button',{name:'发送问题'}).click();
    let turn: {turn_id:string;status:string;result?:unknown;error_code?:string} | undefined;
    await expect.poll(async()=>{
      const response=await request.get(`${api}/courses/learning-fixture/topics/a/agent-turns`,{headers});
      const body=await response.json();
      const items=Array.isArray(body)?body:body.items;
      turn=items.find((t:{turn_id:string})=>!asked.has(t.turn_id));
      return turn ? ['succeeded','failed','canceled'].includes(turn.status) : false;
    },{timeout:100000,intervals:[500,1000,2000]}).toBe(true);
    asked.add(turn!.turn_id);
    log.push({question,seconds:(Date.now()-start)/1000,turn});
    expect(turn!.status, JSON.stringify(turn)).toBe('succeeded');
    return turn!;
  }
  async function waitDelivery(turnId:string) {
    let task: {preparation_id:string;status:string;origin_ref:{message_id:string};result:{resource_refs:{material_id:string;material_type:string;version:number}[]}} | undefined;
    await expect.poll(async()=>{
      const response=await request.get(`${api}/courses/learning-fixture/preparations`,{headers});
      task=(await response.json()).items.find((t:{origin_ref:{message_id:string}})=>t.origin_ref.message_id===`${turnId}:user`);
      return task ? ['succeeded','failed','canceled'].includes(task.status) : false;
    },{timeout:160000,intervals:[1000,2000]}).toBe(true);
    log.push({delivery:task});
    expect(task!.status, JSON.stringify(task)).toBe('succeeded');
    const ref=task!.result.resource_refs[0];
    const notices=page.getByRole('region',{name:'资料准备通知'});
    const details=notices.locator('details');
    if(await details.getAttribute('open')===null) await notices.locator('summary').click();
    const delivered = notices.locator(`article[data-preparation-id="${task!.preparation_id}"]`);
    await expect(delivered.getByRole('button',{name:`打开新${ref.material_type==='quiz'?'练习':'资料'} · v${ref.version}`,exact:true})).toBeEnabled({timeout:15000});
    await delivered.getByRole('button',{name:`打开新${ref.material_type==='quiz'?'练习':'资料'} · v${ref.version}`,exact:true}).click();
    return ref;
  }
  try {
    await ask('请用一个生活中的简单例子解释变量赋值和数学等式的区别。');
    await ask('x = 1; y = x; x = 2。不要直接给答案，只给一步提示引导我判断 y 的值。');
    await ask('请提供一道可以跳过的理解检查，让我试着判断赋值。');
    await page.getByText('检查与学习偏好',{exact:true}).click();
    await expect(page.getByRole('region',{name:'理解检查'}).getByRole('button',{name:'提交检查答案'})).toBeVisible({timeout:15000});
    await page.getByRole('region',{name:'理解检查'}).getByRole('button',{name:'跳过这道检查'}).click();
    const quizTurn=await ask('请生成并保存一份只有一道单选题的变量赋值练习资料。');
    const quizRef=await waitDelivery(quizTurn.turn_id);
    expect(quizRef.material_type).toBe('quiz');
    const frame=page.frameLocator('iframe.sl-live-material');
    await frame.getByRole('checkbox').first().check();
    await frame.getByRole('button',{name:'提交检查答案',exact:true}).click();
    await expect(frame.getByText(/客观批改 ·/)).toBeVisible();
    const docTurn=await ask('请生成并保存一份讲解两个变量赋值过程的补充文档，包含逐行追踪的例子。');
    const original=await waitDelivery(docTurn.turn_id);
    const before=await (await request.get(`${api}/courses/learning-fixture/materials/report/${original.material_id}/versions/1`,{headers})).json();
    expect(before.visibility).toBe('private');
    await expect(frame.locator('main')).toContainText('变量');
    const revisionTurn=await ask('请修改当前这份文档，增加一个交换两个变量的完整例子，保存为个人版本。');
    const revised=await waitDelivery(revisionTurn.turn_id);
    expect(revised.material_id).not.toBe(original.material_id);
    const after=await (await request.get(`${api}/courses/learning-fixture/materials/report/${original.material_id}/versions/1`,{headers})).json();
    expect(after.content).toBe(before.content);
    await expect(frame.locator('main')).toContainText('交换');
    log.push({original:before,revised:await (await request.get(`${api}/courses/learning-fixture/materials/report/${revised.material_id}/versions/1`,{headers})).json()});
    await page.reload();
    await expect(frame.locator('main')).toContainText('交换');
  } finally {
    writeFileSync('../docs/acceptance/artifacts/learning-agent-p6/real-browser.json',JSON.stringify(log,null,2));
  }
});
