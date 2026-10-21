import fs from 'node:fs';
import {checkProject} from '/home/zxqs_ep/Edu_AI/frontend/scripts/check-pbl-project.mjs';
const root='/tmp/pbl-matrix-20261017',out='/home/zxqs_ep/Edu_AI/docs/acceptance/2026-10-17-pbl-e2e-matrix';
const read=p=>JSON.parse(fs.readFileSync(p,'utf8'));
const click=testId=>({type:'click',target:{testId}}),fill=(testId,value)=>({type:'fill',target:{testId},value}),assert=(testId,expected,assertion='text')=>({type:'assert',target:{testId},assertion,expected});
const variants=[
 {name:'score-blue-decrement-noop',case:'score',from:'setBlueScore((s) => Math.max(0, s - 1))',to:'setBlueScore((s) => s)',actions:[click('blue-add'),click('blue-add'),click('blue-minus'),assert('blue-score','1')],requirement:'蓝队已经得分后，减一分确实减少分数'},
 {name:'score-red-negative',case:'score',from:'setRedScore((s) => Math.max(0, s - 1))',to:'setRedScore((s) => s - 1)',actions:[click('red-minus'),assert('red-score','0')],requirement:'红队分数不能低于零'},
 {name:'score-reset-blue-omitted',case:'score',from:'setBlueScore(0);',to:'/* omitted reset for test */',actions:[click('blue-add'),click('reset'),assert('blue-score','0')],requirement:'重置比赛清空双方分数'},
 {name:'form-old-error-retained',case:'form',from:"setMessage('');",to:"if (message.startsWith('报名成功：')) setMessage('');",actions:[click('submit-button'),fill('name-input','小明'),assert('message',0,'count')],requirement:'修改姓名时也清除旧错误提示'},
 {name:'form-trim-omitted',case:'form',from:'name.trim()',to:'name',actions:[fill('name-input','   '),click('submit-button'),assert('message','请输入姓名')],requirement:'空格姓名不能报名'},
];
const result=[];
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
