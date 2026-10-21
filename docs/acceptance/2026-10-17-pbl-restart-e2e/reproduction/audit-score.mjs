import fs from 'node:fs';
import {fileURLToPath} from 'node:url';
import {checkProject} from '../../../../frontend/scripts/check-pbl-project.mjs';
const root=fileURLToPath(new URL('./fresh',import.meta.url)),out=fileURLToPath(new URL('../',import.meta.url));
const read=p=>JSON.parse(fs.readFileSync(p,'utf8'));
const click=testId=>({type:'click',target:typeof testId==='string'?{testId}:testId});
const fill=(testId,value)=>({type:'fill',target:{testId},value});
const assert=(testId,expected,assertion='text')=>({type:'assert',target:typeof testId==='string'?{testId}:testId,assertion,expected});
const team=(color,name)=>({role:'button',name,within:{testId:'team-'+color}});
const variants=[
{name:'score-blue-decrement-noop',case:'score',from:'setBlueScore((prev) => (prev > 0 ? prev - 1 : 0))',to:'setBlueScore((prev) => prev)',actions:[click(team('blue','加 1 分')),click(team('blue','加 1 分')),click(team('blue','减 1 分')),assert('score-blue','1')],requirement:'蓝队从2分减到1分'},
{name:'score-red-negative',case:'score',from:'setRedScore((prev) => (prev > 0 ? prev - 1 : 0))',to:'setRedScore((prev) => prev - 1)',actions:[click(team('red','减 1 分')),assert('score-red','0')],requirement:'红队分数下限0'},
{name:'score-reset-blue-omitted',case:'score',from:'setBlueScore(0);',to:'/* test omitted reset */',actions:[click(team('blue','加 1 分')),click({role:'button',name:'重置比赛'}),assert('score-blue','0')],requirement:'重置双方分数'},
];
while(!fs.existsSync(root+'/matrix_score/private.json'))await new Promise(r=>setTimeout(r,1000));
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
 fs.writeFileSync(out+'/score-mutation-replay.json',JSON.stringify(result,null,2));console.log(v.name,'MISSED',generated.passed);
}
