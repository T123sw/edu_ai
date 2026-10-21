import {test,expect,type Page} from 'playwright/test';
const answer=(ids:string[]=[],text='',blank_values:string[]=[])=>({option_ids:ids,text,blank_values});
const question=(id:string,type:string,number:string,extra={})=>({question_id:id,question_type:type,number,question:id==='q1'?'树的遍历方式是什么？':id==='q2'?'先填写 ____，再填写 ____。':id==='q3'?'解释图的遍历思路。':'计算并说明过程。',blank_count:type==='fill_in_blank'?2:0,children:[],...extra});
const paper={generation_id:'paper-1',title:'数据结构练习',version:'v1',answer_count:4,questions:[question('q1','choice','1',{options:{A:'深度优先',B:'随机访问'}}),question('q2','fill_in_blank','2'),question('q3','short_answer','3'),question('parent','compound','4',{question:'已知树中有四个节点。',children:[question('child','short_answer','4.1')]})]};
type Ans=ReturnType<typeof answer>;
type Attempt={id:string;answer:Ans;status:string;correct:boolean|null;evaluator:string;feedback:string;reference_answer:string;created_at:number};
type Run={id:string;paper_id:string;version:string;status:string;created_at:number;finished_at:number|null;total:number;drafts:Record<string,{answer:Ans;revision:number;submitted?:boolean}>;answers:Record<string,Attempt[]>};
async function setup(page:Page){
  const runs:Run[]=[];const turns:Record<string,unknown>[]=[];let seq=0;let rejectDraft=false;let conflict=false;
  await page.addInitScript(()=>localStorage.setItem('edu-ai-auth',JSON.stringify({token:'fixture',user:{username:'alice',role:'student'}})));
  await page.route('**/api/**',async route=>{
    const url=new URL(route.request().url()),path=url.pathname.replace(/^\/backend/,''),method=route.request().method();const body=method==='GET'?{}:route.request().postDataJSON()||{};
    const ok=(json:unknown,status=200)=>route.fulfill({status,json});
    if(path.endsWith('/auth/verify'))return ok({valid:true,user:{username:'alice',role:'student'}});
    if(path.endsWith('/self-learning/state'))return ok({version:1,rooms:[],resources:[],jobs:[],serverJobs:[],shared:[]});
    if(path==='/api/exam-generations')return ok({items:[{generation_id:'paper-1',job_id:'job-1',status:'succeeded',progress:100,requirement:paper.title,message:'试卷已生成'}]});
    if(path.endsWith('/practice'))return ok(paper);
    if(path.endsWith('/practice-runs')){
      if(method==='GET')return ok({items:[...runs].reverse().map(r=>({...r,submitted:Object.keys(r.answers).length}))});
      const active=runs.find(r=>r.status==='active');if(active&&!body.new)return ok(active);
      const run:Run={id:'run-'+(runs.length+1),paper_id:'paper-1',version:'v1',status:'active',created_at:Date.now()/1000,finished_at:null,total:4,drafts:{},answers:{}};runs.push(run);return ok(run);
    }
    const match=path.match(/practice-runs\/(run-\d+)(.*)$/);
    if(match){const run=runs.find(r=>r.id===match[1])!;const suffix=match[2];
      if(!suffix)return ok(run);
      if(suffix.startsWith('/drafts/')){const id=suffix.split('/').at(-1)!;if(rejectDraft)return ok({detail:'网络暂不可用'},503);if(conflict){conflict=false;run.drafts[id]={answer:answer(['B']),revision:10};return ok({detail:'另一处已更新草稿'},409);}const previous=run.drafts[id];run.drafts[id]={answer:body.answer,revision:(previous?.revision||0)+1};return ok(run.drafts[id]);}
      const add=(id:string,a:Ans)=>{const choice=id==='q1';const saved:Attempt={id:'a-'+(++seq),answer:a,status:choice?'graded':'pending_evaluation',correct:choice?a.option_ids[0]==='A':null,evaluator:choice?'deterministic':'model',feedback:choice?'本题按照深度优先遍历。':'',reference_answer:choice?'A':'',created_at:Date.now()/1000};(run.answers[id]||=[]).push(saved);run.drafts[id]={answer:a,revision:(run.drafts[id]?.revision||0)+1,submitted:true};return saved;};
      if(suffix==='/finish'){Object.entries(body.answers).forEach(([id,a])=>add(id,a as Ans));run.status='finished';run.finished_at=Date.now()/1000;return ok(run);}
      if(suffix.endsWith('/evaluate')){const id=suffix.split('/')[2],aid=suffix.split('/')[3];const a=run.answers[id].find(a=>a.id===aid)!;a.status='graded';a.feedback='AI 参考评价：要点符合';a.reference_answer='遍历全部相邻节点';return ok(a);}
      if(suffix.startsWith('/answers/'))return ok(add(suffix.split('/')[2],body.answer));
    }
    if(path.endsWith('/agent-turns')){
      if(method==='GET')return ok({items:turns});
      const turn={id:'turn-'+(++seq),...body,question_number:body.question_id==='child'?'4.1':body.question_id?.slice(1),answer:'',status:'pending',error:'',created_at:Date.now()/1000,citations:[]};turns.push(turn);return ok(turn,202);
    }
    if(path.endsWith('/cancel')){turns.at(-1)!.status='canceled';return ok(turns.at(-1));}
    if(path.endsWith('/retry')){turns.at(-1)!.status='pending';return ok(turns.at(-1));}
    return ok({items:[]});
  });
  const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
  return {runs,turns,errors,failDraft:(value:boolean)=>{rejectDraft=value;},conflict:()=>{conflict=true;}};
}
for(const width of [1440,390,320])test(`independent exam practice and contextual agent at ${width}px`,async({page})=>{
  await page.setViewportSize({width,height:900});const state=await setup(page);
  await page.goto('/#/exam');await page.getByRole('button',{name:/查看试卷|数据结构练习/}).first().click();
  await expect(page).toHaveURL(/#\/exam\/paper-1$/);await expect(page.getByRole('heading',{name:paper.title})).toBeVisible();
  const q1=page.locator('#exam-question-q1');await q1.getByRole('radio').first().check();await expect(q1.getByRole('status')).toHaveText('已保存');
  await page.reload();await expect(q1.getByRole('radio').first()).toBeChecked();
  await q1.getByRole('button',{name:'提交答案',exact:true}).click();await expect(q1.getByText('回答正确',{exact:true})).toBeVisible();
  await q1.getByRole('button',{name:'讲解',exact:true}).click();const input=page.getByRole('textbox',{name:'向学习 Agent 提问'});await expect(input).toHaveValue(/完整讲解/);
  await page.getByRole('button',{name:'发送问题'}).click();await expect.poll(()=>state.turns.length).toBe(1);expect(state.turns[0].question_id).toBe('q1');expect(state.turns[0].attempt_id).toBeTruthy();
  if(width<760)await page.getByRole('button',{name:'作答',exact:true}).click();
  await page.getByRole('textbox',{name:'第 3 题答案'}).fill('从一个节点开始，逐一访问相邻节点。');
  state.turns[0]={...state.turns[0],status:'succeeded',answer:'第 1 题采用深度优先遍历；先沿一条路径走到底。',citations:[{question_id:'q1',label:'第 1 题'}]};
  if(width<760)await page.getByRole('button',{name:'问答',exact:true}).click();
  await expect(page.getByRole('log')).toContainText('第 1 题采用深度优先遍历');
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2)).toBe(true);
  await page.screenshot({path:`../.runtime/exam-practice-polish/workspace-${width}.png`});
  if(width<760)await page.getByRole('button',{name:'作答',exact:true}).click();
  await expect(page.locator('#exam-question-q3').getByRole('status')).toHaveText('已保存');
  await page.reload();await expect(page.getByRole('textbox',{name:'第 3 题答案'})).toHaveValue('从一个节点开始，逐一访问相邻节点。');
  await expect(q1.getByRole('radio').first()).toBeChecked();expect(state.runs.length).toBe(1);
  await expect(page.getByLabel('作答记录',{exact:true})).toHaveCount(0);
  await expect(page.getByRole('button',{name:/^(重新练习|完成本次练习|看看我的思路)$/})).toHaveCount(0);
  expect(state.errors).toEqual([]);
});
test('offline draft survives refresh and conflict requires an explicit choice',async({page})=>{
  const state=await setup(page);await page.goto('/#/exam/paper-1');const q=page.locator('#exam-question-q1');
  state.failDraft(true);await q.getByRole('radio').first().check();await expect(q.getByRole('alert')).toBeVisible();await page.reload();await expect(q.getByRole('radio').first()).toBeChecked();
  state.failDraft(false);state.conflict();await page.evaluate(()=>window.dispatchEvent(new Event('online')));await q.getByRole('button',{name:'保留本地草稿'}).click();await expect(q.getByRole('status')).toHaveText('已保存');expect(state.runs[0].drafts.q1.answer.option_ids).toEqual(['A']);
});
test('multiple blanks, compound child and evaluation retry retain submitted answers',async({page})=>{
  const state=await setup(page);await page.goto('/#/exam/paper-1');const q2=page.locator('#exam-question-q2');
  await page.getByRole('textbox',{name:'第 2 题第 1 空'}).fill('1');await page.getByRole('textbox',{name:'第 2 题第 2 空'}).fill('2');await q2.getByRole('button',{name:'提交答案',exact:true}).click();
  await expect(q2).toContainText('答案已保存，正在评价');expect(state.runs[0].answers.q2[0].answer.blank_values).toEqual(['1','2']);
  state.runs[0].answers.q2[0].status='evaluation_failed';await q2.getByRole('button',{name:'重新评价'}).click();await expect(q2).toContainText('要点符合');
  await page.getByRole('textbox',{name:'第 4.1 题答案'}).fill('四个节点依次访问');await page.locator('#exam-question-child').getByRole('button',{name:'提示',exact:true}).click();await page.getByRole('button',{name:'发送问题'}).click();
  await expect.poll(()=>state.turns.length).toBe(1);expect(state.turns[0].draft).toEqual(answer([],'四个节点依次访问'));
  await page.getByRole('button',{name:'停止回答'}).click();await expect(page.getByRole('button',{name:'重试回答'})).toBeVisible();
});

for(const width of [1440,390,320])test(`partly visible question can be linked by body click at ${width}px`,async({page})=>{
  await page.setViewportSize({width,height:800});const state=await setup(page);await page.goto('/#/exam/paper-1');
  const card=page.locator('#exam-question-q3');
  await card.evaluate(element=>{element.style.minHeight='1400px';element.scrollIntoView({block:'start'});});
  await card.locator('> .quiz-markdown').click();
  await expect(card.getByRole('button',{name:'关联第 3 题'})).toHaveAttribute('aria-pressed','true');
  const rect=await card.boundingBox();expect(rect!.height).toBeGreaterThan(800);
  if(width<760)await page.getByRole('button',{name:'问答',exact:true}).click();
  await expect(page.locator('.exam-agent-reference')).toContainText('关联第 3 题');
  await page.getByRole('button',{name:'取消题目引用'}).click();
  if(width<760)await page.getByRole('button',{name:'作答',exact:true}).click();
  await card.locator('> .quiz-markdown').click();
  if(width<760)await page.getByRole('button',{name:'问答',exact:true}).click();
  await page.getByRole('textbox',{name:'向学习 Agent 提问'}).fill('为什么这样做？');await page.getByRole('button',{name:'发送问题'}).click();
  await expect.poll(()=>state.turns.length).toBe(1);expect(state.turns[0].question_id).toBe('q3');
  if(width<760)await page.getByRole('button',{name:'作答',exact:true}).click();
  const q1=page.locator('#exam-question-q1');await q1.getByRole('radio').first().check();await q1.getByRole('button',{name:'提交答案',exact:true}).click();
  await page.locator('#exam-question-q2').getByRole('button',{name:'关联第 2 题'}).focus();await page.keyboard.press('Enter');
  await expect(q1.getByRole('button',{name:'关联第 1 题'})).toHaveAttribute('aria-pressed','false');
  await q1.locator('> .quiz-markdown').click();
  await expect(q1.getByRole('button',{name:'关联第 1 题'})).toHaveAttribute('aria-pressed','true');
  expect(state.turns[0].question_id).toBe('q3');expect(state.errors).toEqual([]);
});
test('answer map follows autosaved drafts and restores existing completed answers',async({page})=>{
  const state=await setup(page);await page.goto('/#/exam/paper-1');
  const nav=page.getByRole('navigation',{name:'答题卡'}),q1=page.locator('#exam-question-q1');
  await q1.getByRole('radio').first().check();await expect(nav.getByRole('button',{name:'第 1 题，已填写'})).toBeVisible();
  await expect(nav.getByRole('progressbar')).toHaveAttribute('aria-valuenow','1');
  await q1.getByRole('button',{name:'提交答案',exact:true}).click();await expect(nav.getByRole('button',{name:'第 1 题，已提交'})).toBeVisible();
  state.runs[0].status='finished';state.runs[0].finished_at=Date.now()/1000;await page.reload();
  await expect(q1.getByRole('radio').first()).toBeChecked();await expect(q1).toContainText('回答正确');
  expect(state.runs.length).toBe(1);expect(state.runs[0].answers.q1).toHaveLength(1);
  const option=await q1.locator('.quiz-option').first().boundingBox();expect(option!.height).toBeGreaterThanOrEqual(44);
  expect(await q1.locator('.quiz-option').first().evaluate(el=>getComputedStyle(el).display)).toBe('flex');
  await page.screenshot({path:'../.runtime/exam-practice-polish/workspace-desktop.png'});
});
