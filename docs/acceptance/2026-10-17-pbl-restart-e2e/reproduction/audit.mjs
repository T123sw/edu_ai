import fs from 'node:fs';
import {fileURLToPath} from 'node:url';
import {checkProject} from '../../../../frontend/scripts/check-pbl-project.mjs';
const root=fileURLToPath(new URL('./fresh',import.meta.url)),out=fileURLToPath(new URL('../',import.meta.url));
const read=p=>JSON.parse(fs.readFileSync(p,'utf8'));
const click=testId=>({type:'click',target:typeof testId==='string'?{testId}:testId});
const fill=(testId,value)=>({type:'fill',target:{testId},value});
const assert=(testId,expected,assertion='text')=>({type:'assert',target:typeof testId==='string'?{testId}:testId,assertion,expected});
const variants=[
{name:'form-old-error-retained',case:'form',from:"setMessage('');",to:"if (message.startsWith('报名成功：')) setMessage('');",actions:[click('submit-button'),fill('name-input','小明'),assert('message','')],requirement:'修改姓名清除旧错误'},
{name:'form-trim-omitted',case:'form',from:'name.trim()',to:'name',actions:[fill('name-input','   '),click('submit-button'),assert('message','请输入姓名')],requirement:'空格姓名不能报名'},
];
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
 fs.writeFileSync(out+'/fresh-mutation-replay.json',JSON.stringify(result,null,2));console.log(v.name,'MISSED',generated.passed);
}
