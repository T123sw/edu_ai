import fs from 'node:fs';
import {fileURLToPath} from 'node:url';
import {checkProject} from '../../../../frontend/scripts/check-pbl-project.mjs';
const root=fileURLToPath(new URL('./fresh',import.meta.url)),out=fileURLToPath(new URL('../',import.meta.url));
const read=p=>JSON.parse(fs.readFileSync(p,'utf8'));
const click=testId=>({type:'click',target:typeof testId==='string'?{testId}:testId});
const fill=(testId,value)=>({type:'fill',target:{testId},value});
const assert=(testId,expected,assertion='text')=>({type:'assert',target:typeof testId==='string'?{testId}:testId,assertion,expected});
const add=name=>[fill('item-input',name),click('add-button')];
const variants=[
{name:'shopping-toggle-back-missing',case:'shop_b',from:'purchased: !item.purchased',to:'purchased: true',actions:[...add('牛奶'),click('toggle-button'),click('toggle-button'),assert('toggle-button','待购买')],requirement:'购买状态可往返'},
{name:'shopping-filter-all-noop',case:'shop_b',from:"onClick={() => setFilter('all')}",to:'onClick={() => {}}',actions:[...add('牛奶'),...add('面包'),click({testId:'toggle-button',index:1}),click('filter-purchased'),click('filter-all'),assert('item-row',2,'count')],requirement:'返回全部筛选显示全部'},
{name:'shopping-stats-use-visible-items',case:'shop_b',from:'const kinds = items.length;\n  const pendingUnits = items',to:'const kinds = visibleItems.length;\n  const pendingUnits = visibleItems',actions:[...add('牛奶'),...add('面包'),click({testId:'toggle-button',index:1}),click('filter-purchased'),assert('stat-kinds','2'),assert('stat-pending','1')],requirement:'筛选不影响全局统计'},
];
while(!fs.existsSync(root+'/matrix_shop_b/private.json'))await new Promise(r=>setTimeout(r,1000));
const result=[];

for(const v of variants){
 const d=root+'/matrix_'+v.case;
 const artifact=read(d+'/detail.json').artifact,files=read(d+'/private.json').candidate_private.completed.at(-1).candidate.referenceFiles;
 const source=files['/src/App.jsx'];if(source.split(v.from).length!==2)throw new Error('mutation must match exactly once: '+v.name);
 const checks=[{id:v.name,label:v.requirement,actions:v.actions}];
 const baseline=await checkProject({files,checks});
 const changed={...files,'/src/App.jsx':source.replace(v.from,v.to)};
 const generated=await checkProject({files:changed,checks:artifact.checks});
 const oracle=await checkProject({files:changed,checks});
 if(!baseline.passed||oracle.passed)throw new Error('invalid control: '+v.name+JSON.stringify({baseline,oracle}));
 result.push({name:v.name,case:v.case,requirement:v.requirement,baselinePasses:baseline.passed,generatedAcceptancePasses:generated.passed,independentRequirementPasses:oracle.passed,missedByGeneratedChecks:generated.passed,generated,oracle});
 fs.writeFileSync(out+'/shopping-mutation-replay.json',JSON.stringify(result,null,2));console.log(v.name,'MISSED',generated.passed);
}
