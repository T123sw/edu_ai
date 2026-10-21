import {chromium} from 'playwright';
import fs from 'node:fs';
// Inspect a genuinely generated artifact; API transport here is mocked for visual QA only.
const artifact=JSON.parse(fs.readFileSync(process.argv[2] || '/tmp/edu-practice-generated.json','utf8'));
const browser=await chromium.launch();
const page=await browser.newPage({viewport:{width:1560,height:1100}});
await page.addInitScript(()=>localStorage.setItem('edu-ai-auth',JSON.stringify({token:'acceptance',user:{username:'practice_acceptance',role:'student'}})));
await page.route('**/api/**',async route=>{
 const path=new URL(route.request().url()).pathname;
 if(path.endsWith('/auth/verify'))return route.fulfill({json:{valid:true,user:{username:'practice_acceptance',role:'student'}}});
 if(path.endsWith('/self-learning/state'))return route.fulfill({json:{version:1,rooms:[],resources:[],jobs:[],serverJobs:[],shared:[]}});
 if(path.endsWith('/practice/preview'))return route.fulfill({json:{id:'preview',job:{status:'succeeded'},artifact,journal:{observations:[],messages:[]}}});
 return route.fulfill({json:{items:[]}});
});
await page.goto('http://127.0.0.1:5206/#/practice/preview');
await page.getByRole('heading',{name:artifact.plan.concept_name,exact:true}).waitFor();
await page.waitForTimeout(1200);
const frame=page.frames().find(f=>f!==page.mainFrame());
const initial=await frame.evaluate(()=>window.EduPractice.snapshot());
const controls=await frame.locator('[data-param]').evaluateAll(els=>els.map(e=>({name:e.dataset.param,type:e.type,min:e.min,max:e.max,value:e.value})));
await page.screenshot({path:'../docs/acceptance/2026-10-13-interactive-practice/desktop.png',fullPage:true});
await page.setViewportSize({width:390,height:950});
await page.waitForTimeout(300);
await page.screenshot({path:'../docs/acceptance/2026-10-13-interactive-practice/mobile.png',fullPage:true});
console.log(JSON.stringify({initial,controls,validation:artifact.validation,title:artifact.plan.concept_name},null,2));
await browser.close();
