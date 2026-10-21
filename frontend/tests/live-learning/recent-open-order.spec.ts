import {test,expect,type BrowserContext,type Page} from 'playwright/test';
import {seedState} from '../../src/selfLearning/model';

async function setup(context:BrowserContext){
  const state=seedState();state.rooms=state.rooms.slice(0,2);state.rooms.forEach((room,i)=>{room.title=['较新课堂','较早课堂'][i];room.updatedAt=200-i*100;});state.resources=[];
  let username='recent-alice';
  await context.addInitScript(()=>{if(!localStorage.getItem('edu-ai-auth'))localStorage.setItem('edu-ai-auth',JSON.stringify({token:'fixture',user:{username:'recent-alice',role:'student'}}));});
  const resources=[{material_id:'new',material_type:'report',title:'较新报告',version:1},{material_id:'old',material_type:'report',title:'较早报告',version:1}].map(r=>({...r,updated_at:'2026-10-15T00:00:00Z',studio_course_id:state.rooms[0].id,studio_chapter_id:state.rooms[0].chapters[0].id}));
  await context.route('**/api/**',route=>{
    const path=new URL(route.request().url()).pathname.replace(/^\/backend/,'');
    if(path.endsWith('/auth/verify'))return route.fulfill({json:{valid:true,user:{username,role:'student'}}});
    if(path.endsWith('/self-learning/state'))return route.fulfill({json:{...state,shared:[],serverJobs:[]}});
    const room=state.rooms.find(r=>path.endsWith('/courses/'+r.id)||path.endsWith('/courses/'+r.id+'/learning'));
    if(room)return route.fulfill({json:room});
    if(path==='/api/practice')return route.fulfill({json:{items:[{id:'new',topic:'较新实验',status:'succeeded'},{id:'old',topic:'较早实验',status:'succeeded'}]}});
    if(path==='/api/pbl')return route.fulfill({json:{items:[{exerciseId:'new',topic:'较新项目',status:'ready'},{exerciseId:'old',topic:'较早项目',status:'ready'}]}});
    if(path.startsWith('/api/practice/'))return route.fulfill({json:{id:path.split('/').pop(),artifact:null,job:{status:'queued',input_summary:{}},journal:{messages:[],observations:[]}}});
    if(path.startsWith('/api/pbl/'))return route.fulfill({json:{exerciseId:path.split('/').pop(),artifact:null,job:{status:'queued'}}});
    if(path==='/api/personal-studio')return route.fulfill({json:{resources,jobs:[]}});
    if(path.startsWith('/api/personal-studio/resources/'))return route.fulfill({json:{...resources.find(r=>path.endsWith('/'+r.material_id)),content:'# 报告\n\n测试正文。'}});
    return route.fulfill({json:{items:[],preparations:[]}});
  });
  return {state,switchUser:(name:string)=>{username=name;}};
}
const titles=(page:Page,section:string)=>page.getByRole('region',{name:section,exact:true}).locator('.sl-class-card h3');

test('首页课堂按最近点击排序，刷新、搜索及后台更新保持顺序',async({page,context})=>{
  const {state}=await setup(context);await page.goto('/');
  await expect(titles(page,'最近学习')).toHaveText(['较新课堂','较早课堂']);
  await page.getByRole('button',{name:/较早课堂/}).click();await expect(page).toHaveURL(new RegExp(state.rooms[1].id));
  await page.goto('/');await expect(titles(page,'最近学习')).toHaveText(['较早课堂','较新课堂']);
  state.rooms[0].updatedAt=Date.now()+100000;await page.reload();await expect(titles(page,'最近学习')).toHaveText(['较早课堂','较新课堂']);
  await page.getByRole('button',{name:'搜索课堂',exact:true}).click();await page.getByRole('textbox',{name:'搜索课堂',exact:true}).fill('较早');await expect(titles(page,'最近学习')).toHaveText(['较早课堂']);
  await page.getByRole('textbox',{name:'搜索课堂',exact:true}).fill('');await page.getByRole('button',{name:/较新课堂/}).click();await expect(page).toHaveURL(new RegExp(state.rooms[0].id));
  await page.goto('/');await expect(titles(page,'最近学习')).toHaveText(['较新课堂','较早课堂']);
});

test('实验、PBL 列表独立排序，兼容入口和刷新保留访问顺序',async({page,context})=>{
  await setup(context);await page.goto('/#/practice');
  for(const [section,noun,route] of [['我的实验','实验','/practice/old'],['我的项目','项目','/practice/code/old']]){
    await expect(titles(page,section)).toHaveText([`较新${noun}`,`较早${noun}`]);
    await page.getByRole('button',{name:new RegExp(`较早${noun}`)}).click();await expect(page).toHaveURL(new RegExp(route+'$'));
    await page.goto('/#/practice');await expect(titles(page,section)).toHaveText([`较早${noun}`,`较新${noun}`]);
    await page.reload();await expect(titles(page,section)).toHaveText([`较早${noun}`,`较新${noun}`]);
  }
  await page.goto('/#/practice/code');await expect(titles(page,'我的项目')).toHaveText(['较早项目','较新项目']);
  await expect(titles(page,'我的实验')).toHaveText(['较早实验','较新实验']);
});

test('资源打开即重排，刷新、标签页同步和账号隔离',async({page,context})=>{
  const fixture=await setup(context);await page.goto('/#/my-resources');
  const rows=page.locator('.studio-resource-title strong');await expect(rows).toHaveText(['较新报告','较早报告']);
  const tab=await context.newPage();await tab.goto('/#/my-resources');await expect(tab.locator('.studio-resource-title strong')).toHaveText(['较新报告','较早报告']);
  await page.locator('.studio-resource-row').filter({hasText:'较早报告'}).click();await page.getByRole('button',{name:'关闭工具面板'}).click();
  await expect(rows).toHaveText(['较早报告','较新报告']);await expect(tab.locator('.studio-resource-title strong')).toHaveText(['较早报告','较新报告']);
  await page.reload();await expect(rows).toHaveText(['较早报告','较新报告']);
  await page.goto('/#/classroom/'+fixture.state.rooms[0].id);await page.getByRole('button',{name:'打开生成工具'}).click();
  await expect(page.locator('.studio-course-resource strong')).toHaveText(['较早报告','较新报告']);
  await page.getByRole('button',{name:'关闭工具面板'}).click();await page.goto('/#/my-resources');
  await tab.locator('.studio-resource-row').filter({hasText:'较新报告'}).click();await expect(rows).toHaveText(['较新报告','较早报告']);await tab.close();
  await page.locator('.studio-resource-row').filter({hasText:'较早报告'}).click();await page.getByRole('button',{name:'关闭工具面板'}).click();
  fixture.switchUser('recent-bob');await page.evaluate(()=>localStorage.setItem('edu-ai-auth',JSON.stringify({token:'fixture',user:{username:'recent-bob',role:'student'}})));await page.reload();await expect(rows).toHaveText(['较新报告','较早报告']);
  fixture.switchUser('recent-alice');await page.evaluate(()=>localStorage.setItem('edu-ai-auth',JSON.stringify({token:'fixture',user:{username:'recent-alice',role:'student'}})));await page.reload();await expect(rows).toHaveText(['较早报告','较新报告']);
});


test('旧资源中心与我的资源共用同一份打开记录',async({page,context})=>{
  const {state}=await setup(context),room=state.rooms[0];
  const template=room.chapters[0].resources[0];
  state.resources=['new','old'].map((id,i)=>({...template,id:'legacy-'+id,title:i?'较早旧资源':'较新旧资源',kind:'report',createdAt:200-i*100,courseId:room.id,remote:{materialType:'report',materialId:id,courseId:room.id,version:1,visibility:'private'}}));
  await page.goto('/#/resources');
  await expect(page.locator('.sl-library-item strong')).toHaveText(['较新旧资源','较早旧资源']);
  await page.getByRole('button',{name:/较早旧资源/}).click();await expect(page.locator('.sl-library-item strong')).toHaveText(['较早旧资源','较新旧资源']);
  await page.goto('/#/my-resources');await expect(page.locator('.studio-resource-title strong').first()).toHaveText('较早旧资源');
  await page.locator('.studio-resource-row').filter({hasText:'较新旧资源'}).click();await page.getByRole('button',{name:'关闭工具面板'}).click();
  await page.goto('/#/resources');await expect(page.locator('.sl-library-item strong')).toHaveText(['较新旧资源','较早旧资源']);
});
