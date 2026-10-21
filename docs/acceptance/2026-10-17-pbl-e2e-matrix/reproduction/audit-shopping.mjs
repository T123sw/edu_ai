import fs from 'node:fs';
import {checkProject} from '/home/zxqs_ep/Edu_AI/frontend/scripts/check-pbl-project.mjs';
const root='/tmp/pbl-matrix-20261017',out='/home/zxqs_ep/Edu_AI/docs/acceptance/2026-10-17-pbl-e2e-matrix';
const read=p=>JSON.parse(fs.readFileSync(p,'utf8'));
const click=testId=>({type:'click',target:{testId}}),fill=(testId,value)=>({type:'fill',target:{testId},value}),assert=(testId,expected,assertion='text')=>({type:'assert',target:{testId},assertion,expected});
const variants=[
 {name:'shopping-toggle-back-missing',case:'shop_a',from:'purchased: !item.purchased',to:'purchased: true',actions:[fill('item-name-input','牛奶'),click('add-button'),click('item-toggle'),click('item-toggle'),assert('item-status','待购买')],requirement:'已购买商品可以切换回待购买'},
 {name:'shopping-filter-all-noop',case:'shop_a',from:`data-testid="filter-all" onClick={() => setFilter('all')}`,to:`data-testid="filter-all" onClick={() => {}}`,actions:[fill('item-name-input','牛奶'),click('add-button'),fill('item-name-input','面包'),click('add-button'),{type:'click',target:{role:'button',name:'切换 面包 的购买状态'}},click('filter-purchased'),click('filter-all'),assert('item-name',2,'count')],requirement:'从筛选返回全部时重新显示所有商品'},
 {name:'shopping-stats-use-visible-items',case:'shop_a',from:'const kindCount = items.length;\n  const pendingTotal = items',to:'const kindCount = visibleItems.length;\n  const pendingTotal = visibleItems',actions:[fill('item-name-input','牛奶'),click('add-button'),fill('item-name-input','面包'),click('add-button'),{type:'click',target:{role:'button',name:'切换 面包 的购买状态'}},click('filter-purchased'),assert('stats-kind-count','2'),assert('stats-pending-total','1')],requirement:'筛选不能改变全清单统计'},
];
const result=read(out+'/mutation-audit.json');
for(const v of variants){
 const data=root+'/matrix_'+v.case;
 const artifact=read(data+'/detail.json').artifact,files=read(data+'/private.json').candidate_private.completed.at(-1).candidate.referenceFiles;
 const source=files['/src/App.jsx'];if(source.split(v.from).length!==2)throw new Error('mutation does not match exactly once: '+v.name);
 const checks=[{id:v.name,label:v.requirement,actions:v.actions}];
 const baseline=await checkProject({files,checks});
 const changed={...files,'/src/App.jsx':source.replace(v.from,v.to)};
 const generated=await checkProject({files:changed,checks:artifact.checks});
 const oracle=await checkProject({files:changed,checks});
 if(!baseline.passed||oracle.passed)throw new Error('invalid negative control: '+v.name);
 const item={name:v.name,case:v.case,requirement:v.requirement,baselinePasses:baseline.passed,generatedAcceptancePasses:generated.passed,independentRequirementPasses:oracle.passed,missedByGeneratedChecks:generated.passed,generated,oracle};result.push(item);
 fs.writeFileSync(out+'/mutation-audit.json',JSON.stringify(result,null,2));console.log(v.name,'missed:',item.missedByGeneratedChecks);
}
