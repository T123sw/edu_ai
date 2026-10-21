const {chromium,expect}=require('/home/zxqs_ep/Edu_AI/frontend/node_modules/playwright/test');
const fs=require('node:fs');
(async()=>{
 const [base,label]=process.argv.slice(2), browser=await chromium.launch({headless:true}),results=[];
 try {for(const width of [1440,390,320]){
  const page=await browser.newPage({viewport:{width,height:1000}}),errors=[],posts=[];
  let populated=false,uploaded=0;
  page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>localStorage.setItem('edu-ai-auth',JSON.stringify({token:'fixture',user:{username:'exam_style_check',role:'student'}})));
  await page.route('**/api/**',async route=>{
   const req=route.request(),path=new URL(req.url()).pathname.replace(/^\/backend/,''),method=req.method();
   let json={items:[]},status=200;
   if(path.endsWith('/auth/verify'))json={valid:true,user:{username:'exam_style_check',role:'student'}};
   if(path.endsWith('/self-learning/state'))json={version:1,rooms:[],resources:[],jobs:[],serverJobs:[],shared:[]};
   if(path==='/api/exam-generations'){
    if(method==='POST'){posts.push(req.postDataJSON());json={generation_id:'new'};status=202;}
    else json={items:populated?['succeeded','failed','running','queued','succeeded'].map((status,i)=>({generation_id:'g'+i,job_id:'j'+i,status,progress:40,requirement:['数据结构期末模拟试卷','算法复习试卷','离散数学练习','计算机网络模拟题','操作系统试卷'][i],message:status==='running'?'正在生成题目':'试卷生成记录'})):[]};
   }
   if(path.endsWith('/documents')){uploaded++;json={document_id:'d'+uploaded,filename:uploaded===1?'数据结构真题.pdf':'复习资料.pdf'};status=201;}
   if(path.endsWith('/retry')){posts.push({retry:path});json={edu_job_id:'retry'};status=202;}
   if(path.endsWith('/paper'))json={questions:[{question_id:'q1',question_type:'compound',question:'公共条件：数组长度为 8。\n\na) 写出快速排序复杂度。',children:[{question_id:'q1a',question_type:'short_answer',question:'写出快速排序复杂度。',children:[]}]}]};
   await route.fulfill({status,json});
  });
  await page.goto(base+'/#/exam');
  await expect(page.getByRole('heading',{name:'认真答，看见自己的进步。'})).toBeVisible();
  await expect(page.locator('.sl-editorial-illustration')).toBeVisible();
  const submit=page.getByRole('button',{name:'生成模拟试卷',exact:true});
  await expect(submit).toBeDisabled();
  await expect(page.getByText('还没有试卷，上传资料开始准备下一场考试。')).toBeVisible();
  await page.screenshot({path:__dirname+`/${label}-${width}-empty.png`,fullPage:true});
  await page.getByRole('textbox',{name:'考试范围与目标'}).fill('保留题型与题数，生成新的数据结构试卷。');
  await page.locator('input[type=file]').setInputFiles({name:'数据结构真题.pdf',mimeType:'application/pdf',buffer:Buffer.from('%PDF-fixture')});
  await expect(page.getByRole('radio',{name:'参考试卷'})).toBeChecked();
  await expect(submit).toBeEnabled();
  await submit.click();await expect.poll(()=>posts.length).toBe(1);
  expect(posts[0].mode).toBe('mimic');expect(posts[0].sources).toEqual([{document_id:'d1',role:'template'}]);
  await page.getByRole('combobox',{name:'出题方式'}).selectOption('custom');
  await page.getByRole('spinbutton',{name:'题目数量'}).fill('6');
  await submit.click();await expect.poll(()=>posts.length).toBe(2);
  expect(posts[1].num_questions).toBe(6);expect(posts[1].sources[0].role).toBe('context');
  await page.getByRole('button',{name:'移除',exact:true}).click();await expect(submit).toBeDisabled();expect(posts.length).toBe(2);
  populated=true;await page.reload();
  await expect(page.locator('.exam-task')).toHaveCount(4);
  await page.getByRole('button',{name:'查看全部',exact:true}).click();await expect(page.locator('.exam-task')).toHaveCount(5);
  await page.getByRole('button',{name:'收起',exact:true}).click();
  await page.getByRole('button',{name:'搜索试卷',exact:true}).click();await page.getByRole('textbox',{name:'搜索试卷'}).fill('数据结构');await expect(page.locator('.exam-task')).toHaveCount(1);
  await page.getByRole('button',{name:'关闭试卷搜索'}).click();
  await page.getByRole('button',{name:/重试生成/}).click();await expect.poll(()=>posts.length).toBe(3);expect(posts[2].retry).toBe('/api/jobs/j1/retry');
  await page.getByRole('button',{name:/数据结构期末模拟试卷.*查看试卷/}).click();
  const paper=page.getByRole('region',{name:'试卷预览'});await expect(paper).toBeVisible();
  expect((await paper.textContent()).split('写出快速排序复杂度。').length-1).toBe(1);
  await expect(paper.getByText('公共条件：数组长度为 8。')).toBeVisible();
  await paper.getByRole('button',{name:'关闭预览'}).click();
  for(const [theme,name] of [['forest','纸间绿'],['ocean','雾海蓝'],['dark','石墨夜']]){
   await page.getByRole('button',{name:'页面配色',exact:true}).click();await page.getByRole('dialog',{name:'页面配色'}).getByRole('button',{name:new RegExp(name)}).click();
   await page.screenshot({path:__dirname+`/${label}-${width}-${theme}.png`,fullPage:true});
   expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  }
  for(const [path,heading] of [['/','让好奇，成为你的下一堂课。'],['/practice','动手试，让原理变得看得见。']]){
   await page.goto(base+'/#'+path);await expect(page.getByRole('heading',{name:heading})).toBeVisible();
   const input=page.locator('.sl-prompt textarea');await expect(input).toBeEnabled();await input.fill('保留原来的首页功能');await expect(page.locator('.sl-prompt button[type=submit]')).toBeEnabled();
  }
  expect(errors).toEqual([]);results.push({width,empty:true,upload:true,mimic:true,custom:true,remove:true,search:true,expand:true,retry:true,preview:true,themes:3,otherHomes:true,errors});await page.close();
 }
 fs.writeFileSync(__dirname+`/${label}-results.json`,JSON.stringify({base,api:'fixtures; no production writes or model calls',results},null,2)+'\n');console.log(JSON.stringify(results));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
