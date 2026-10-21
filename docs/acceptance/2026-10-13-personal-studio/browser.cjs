const {chromium}=require('/home/zxqs_ep/Edu_AI/frontend/node_modules/playwright');
const assert=require('node:assert/strict');
(async()=>{const browser=await chromium.launch();try{for(const width of [1440,1024,390,320]){
const page=await browser.newPage({viewport:{width,height:900}});page.setDefaultTimeout(12000);const errors=[],posts=[];page.on('pageerror',e=>errors.push(e.message));
let jobs=[],resources=[];
const room={id:'course-a',title:'Python 入门',goal:'学习变量',tone:'mint',chapters:[{id:'variables',title:'变量与类型',resources:[]}],progress:{},understanding:{},messages:[],updatedAt:1};
await page.addInitScript(()=>localStorage.setItem('edu-ai-auth',JSON.stringify({token:'fixture',user:{username:'learner',role:'student'}})));
await page.route('**/api/**',async route=>{const url=new URL(route.request().url()),path=url.pathname.replace(/^\/backend/,'');if(!path.startsWith('/api/'))return route.continue();let data={items:[]};
if(path.endsWith('/auth/verify'))data={valid:true,user:{username:'learner',role:'student'}};
else if(path==='/api/self-learning/state')data={version:1,rooms:[room],resources:[],jobs:[],shared:[],serverJobs:jobs};
else if(path==='/api/course-preparations')data={preparations:[]};
else if(path==='/api/personal-studio')data={jobs,resources};
else if(path==='/api/personal-studio/generate') {const body=route.request().postDataJSON();posts.push(body);data={edu_job_id:'job-'+posts.length,status:'running',kind:'generate_report',progress:18,message:'正在搜索并读取资料',cancelable:true,input_summary:{title:body.title,source:'personal-studio'}};jobs.push(data);}
else if(path.endsWith('/attach')) {posts.push(route.request().postDataJSON());data=room;}
else if(path.startsWith('/api/personal-studio/resources/')) data={material_id:'report-1',material_type:'report',title:'研究报告',content:'# 研究结论\n\n这是根据资料整理的内容。\n\n## 应用\n\n通过实例解释。',research_sources:[{title:'原始资料',url:'https://example.org',content:'来源正文'}]};
else if(path.endsWith('/cancel')) {jobs=jobs.map(j=>({...j,status:'canceled'}));data=jobs[0];}
return route.fulfill({json:data});});
await page.goto('http://127.0.0.1:5304/');await page.getByRole('button',{name:'打开深度研究'}).waitFor();await page.evaluate(()=>document.fonts.ready);
assert.equal(await page.getByRole('button',{name:'打开生成工具'}).count(),1);
assert.equal(await page.getByRole('tab',{name:'我的课程'}).getAttribute('aria-selected'),'true');
await page.screenshot({path:`/tmp/edu-personal-studio/home-${width}.png`,fullPage:true});
assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
await page.getByRole('button',{name:'打开深度研究'}).click();await page.getByRole('dialog',{name:'深度研究'}).waitFor();
await page.getByLabel('想深入了解什么？').fill('RAG 与长上下文模型的区别');await page.getByRole('button',{name:'开始研究',exact:true}).click();await page.getByText('任务已开始，完成后自动保存到「我的资源」。可以关闭面板，继续学习。').waitFor();assert.equal(posts[0].mode,'research');assert.equal(posts[0].title,'RAG 与长上下文模型的区别');
await page.getByRole('button',{name:'关闭工具面板'}).click();assert.equal(await page.getByRole('tab',{name:/我的资源/}).getAttribute('aria-selected'),'true');await page.getByText('正在搜索并读取资料 · 18%').waitFor();
await page.getByRole('button',{name:'打开生成工具'}).click();await page.getByRole('dialog').getByRole('button',{name:/思维导图/}).click();await page.getByLabel(/思维导图主题/).fill('数组与链表');await page.getByRole('button',{name:'开始生成',exact:true}).click();await page.getByText('任务已开始，完成后自动保存到「我的资源」。可以关闭面板，继续学习。').waitFor();assert.equal(posts[1].resource_type,'graph');assert.equal(posts[1].config.title,'数组与链表');assert.equal(posts[1].config.max_depth,3);assert(!posts[1].config.course_id);
await page.getByRole('button',{name:'全部工具'}).click();assert.equal(await page.locator('.studio-tool-grid>button').count(),4);
await page.screenshot({path:`/tmp/edu-personal-studio/tools-${width}.png`});await page.keyboard.press('Escape');assert.equal(await page.getByRole('dialog').count(),0);
resources=[{material_id:'report-1',material_type:'report',title:'研究报告',studio_title:'RAG 与长上下文模型的区别',studio_mode:'research',version:1,updated_at:new Date().toISOString()}];jobs=[];
await page.reload();await page.getByRole('tab',{name:'我的资源'}).click();await page.getByRole('button',{name:/RAG 与长上下文模型的区别/}).click();await page.getByRole('heading',{name:'研究结论'}).waitFor();await page.getByText('参考来源 · 1').click();assert.equal(await page.getByRole('link',{name:/原始资料/}).getAttribute('href'),'https://example.org');
await page.getByRole('button',{name:'加入课程',exact:true}).click();await page.getByLabel('课程',{exact:true}).selectOption('course-a');await page.getByLabel('知识点',{exact:true}).selectOption('variables');await page.getByRole('button',{name:'确认加入'}).click();await page.getByText('已加入课程，原始资源仍保留在我的资源。').waitFor();assert.equal(posts.at(-1).chapter_id,'variables');await page.screenshot({path:`/tmp/edu-personal-studio/preview-${width}.png`});
await page.keyboard.press('Escape');
for(const theme of ['ocean','sunset','dark']){await page.evaluate(t=>{localStorage.setItem('stitch-theme',t)},theme);await page.reload();await page.getByRole('button',{name:'打开生成工具'}).click();await page.screenshot({path:`/tmp/edu-personal-studio/tools-${width}-${theme}.png`});const box=await page.getByRole('dialog').boundingBox();assert(box.x>=0&&box.x+box.width<=width+.1);await page.keyboard.press('Escape');}
assert.deepEqual(errors,[]);console.log(`PASS ${width}: home, research, background job, tool configuration, reload, sources, course attachment, themes, overflow`);await page.close();
}}finally{await browser.close()}})().catch(e=>{console.error(e);process.exit(1)});
