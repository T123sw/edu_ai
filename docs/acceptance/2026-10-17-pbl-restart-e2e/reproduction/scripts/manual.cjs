const {chromium,expect}=require('/home/zxqs_ep/Edu_AI/frontend/node_modules/playwright/test');
const fs=require('node:fs');
const root='/tmp/pbl-restart-20261017',out='/home/zxqs_ep/Edu_AI/docs/acceptance/2026-10-17-pbl-restart-e2e';
const read=p=>JSON.parse(fs.readFileSync(p,'utf8'));
async function enter(page){const stage=page.locator('.pbl-workbench-stage');await stage.waitFor();if(Math.abs((await stage.boundingBox()).y)>2)await page.getByRole('button',{name:'展开工作区',exact:true}).click();}
(async()=>{
 const browser=await chromium.launch({headless:true});const results=[];
 try{for(const name of ['score','form','shop_b','layout']){
  while(!fs.existsSync(out+'/'+name+'-browser.json'))await new Promise(r=>setTimeout(r,1000));
  const a=read(root+'/matrix_'+name+'/detail.json').artifact,auth=read(root+'/matrix_'+name+'/auth.json');
  const ctx=await browser.newContext({viewport:{width:1440,height:1000},serviceWorkers:'block'});await ctx.addInitScript(auth=>localStorage.setItem('edu-ai-auth',JSON.stringify(auth)),auth);
  const page=await ctx.newPage();const result={name,independentBusinessScenarios:[],viewports:[]};page.setDefaultTimeout(60000);
  await page.route('**/api/**',async route=>{const u=new URL(route.request().url());try{await route.fulfill({response:await route.fetch({url:'http://127.0.0.1:8027'+u.pathname.replace(/^\/backend/,'')+u.search,timeout:120000})});}catch{await route.abort();}});
  try{
   await page.goto('http://127.0.0.1/#/practice/code/'+a.exerciseId);await enter(page);await page.getByRole('button',{name:'页面预览',exact:true}).click();
   const f=page.frameLocator('.sp-preview iframe');await expect(f.locator('#root')).not.toBeEmpty({timeout:90000});
   const t=id=>f.getByTestId(id),btn=name=>f.getByRole('button',{name,exact:true});
   if(name==='score'){
    await f.getByTestId('team-blue').getByRole('button',{name:'加 1 分',exact:true}).click();await f.getByTestId('team-blue').getByRole('button',{name:'加 1 分',exact:true}).click();await f.getByTestId('team-blue').getByRole('button',{name:'减 1 分',exact:true}).click();await expect(t('score-blue')).toHaveText('1');await expect(t('score-red')).toHaveText('0');
    await f.getByTestId('team-red').getByRole('button',{name:'减 1 分',exact:true}).click();await expect(t('score-red')).toHaveText('0');
    await f.getByTestId('team-red').getByRole('button',{name:'加 1 分',exact:true}).click();await f.getByTestId('team-red').getByRole('button',{name:'加 1 分',exact:true}).click();await expect(t('status')).toHaveText('红队领先');await f.getByTestId('team-red').getByRole('button',{name:'减 1 分',exact:true}).click();await expect(t('status')).toHaveText('平局');
    await btn('重置比赛').click();await expect(t('score-red')).toHaveText('0');await expect(t('score-blue')).toHaveText('0');result.independentBusinessScenarios=['蓝队正数减分','红队零分下限','双方互不影响','领先与平局','重置双方'];
   }else if(name==='form'){
    await t('submit-button').click();await expect(t('message')).toHaveText('请输入姓名');await t('name-input').fill('小明');await expect(t('message')).toHaveText('');
    await t('name-input').fill('  小明  ');await t('submit-button').click();await expect(t('message')).toHaveText('报名成功：小明');await t('name-input').fill('小红');await expect(t('message')).toHaveText('');
    await t('name-input').fill('   ');await t('submit-button').click();await expect(t('message')).toHaveText('请输入姓名');result.independentBusinessScenarios=['空白拦截','去掉首尾空格','修改清除成功消息','修改清除错误消息'];
   }else if(name==='shop_b'){
    const row=i=>t('item-row').nth(i);
    const add=async name=>{await t('item-input').fill(name);await t('add-button').click();};
    await add('   ');await expect(t('error-message')).toBeVisible();await expect(t('item-row')).toHaveCount(0);
    await add('牛奶');await expect(t('item-input')).toHaveValue('');await t('decrease-button').click();await expect(t('item-quantity')).toHaveText('1');
    await add('面包');await row(0).getByTestId('increase-button').click();await expect(t('item-quantity')).toHaveText(['2','1']);await expect(t('stat-pending')).toHaveText('3');
    await row(0).getByTestId('toggle-button').click();await expect(t('toggle-button')).toHaveText(['已购买','待购买']);await t('filter-purchased').click();await expect(t('item-row')).toHaveCount(1);await expect(t('stat-kinds')).toHaveText('2');await expect(t('stat-pending')).toHaveText('1');
    await t('toggle-button').click();await expect(t('item-row')).toHaveCount(0);await expect(t('stat-pending')).toHaveText('3');await t('filter-all').click();await expect(t('item-row')).toHaveCount(2);
    await row(0).getByTestId('toggle-button').click();await row(1).getByTestId('delete-button').click();await expect(t('stat-kinds')).toHaveText('1');await expect(t('stat-pending')).toHaveText('0');result.independentBusinessScenarios=['空白拦截与清空输入','数量下限','两商品独立操作','购买状态往返','全部筛选恢复','筛选不影响统计','删除更新统计'];
   }else{
    await expect(f.getByRole('heading',{name:'我的作品',exact:true})).toBeVisible();for(const title of ['天气卡片','读书笔记','像素画'])await expect(f.getByRole('heading',{name:title,exact:true})).toBeVisible();
    const title=await f.getByRole('heading',{name:'我的作品',exact:true}).boundingBox(),intro=await f.getByText('记录我的学习成果',{exact:true}).boundingBox(),list=await f.getByRole('heading',{name:'天气卡片',exact:true}).boundingBox();expect(title.y+title.height).toBeLessThanOrEqual(intro.y);expect(intro.y+intro.height).toBeLessThanOrEqual(list.y);result.independentBusinessScenarios=['标题与简介顺序','作品区域位置','三件作品均展示'];
   }
   await page.screenshot({path:out+'/'+name+'-interaction.png',fullPage:true});
   for(const width of [1440,390,320]){
    await page.setViewportSize({width,height:900});if(width<=390)await page.getByRole('button',{name:'预览与验收',exact:true}).click();
    const metrics=await f.locator('body').evaluate(e=>({viewport:innerWidth,scrollWidth:document.documentElement.scrollWidth,bodyWidth:e.scrollWidth,bodyHeight:e.scrollHeight,text:e.innerText.slice(0,250)}));
    result.viewports.push({outerWidth:width,outerNoOverflow:await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),previewNoHorizontalOverflow:metrics.scrollWidth<=metrics.viewport+1,...metrics});
   }
   result.passed=true;
  }catch(e){result.passed=false;result.error=e.stack;await page.screenshot({path:out+'/'+name+'-manual-failure.png',fullPage:true}).catch(()=>{});}
  finally{results.push(result);fs.writeFileSync(out+'/independent-preview.json',JSON.stringify(results,null,2));await ctx.close();console.log(name,JSON.stringify(result));}
 }}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
