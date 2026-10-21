import fs from 'node:fs';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
import {checkProject} from '../../../../frontend/scripts/check-pbl-project.mjs';
const require=createRequire(import.meta.url),{withFiles}=require('./runtime.cjs');
const root=fileURLToPath(new URL('./fixtures',import.meta.url)),out=fileURLToPath(new URL('./replay',import.meta.url)),read=p=>JSON.parse(fs.readFileSync(p));
const d=root+'/matrix_csv',a=read(d+'/detail.json').artifact,files=read(d+'/private.json').candidate_private.completed.at(-1).candidate.referenceFiles;
const variants=[
{name:'average-rounded-to-integer',from:'(records.reduce((sum, r) => sum + r.score, 0) / count).toFixed(2)',to:'Math.round(records.reduce((sum, r) => sum + r.score, 0) / count).toFixed(2)',oracle:async(p,e)=>{await p.getByTestId('score-input').fill('甲,0\n乙,100\n丙,50.5');await p.getByTestId('analyze-button').click();await e(p.getByTestId('stat-average')).toHaveText('50.17');}},
{name:'reanalyze-appends-old-records',from:'setRecords(result.records);',to:'setRecords([...records,...result.records]);',oracle:async(p,e)=>{await p.getByTestId('score-input').fill('甲,60');await p.getByTestId('analyze-button').click();await p.getByTestId('score-input').fill('乙,80');await p.getByTestId('analyze-button').click();await e(p.getByTestId('stat-count')).toHaveText('1');}},
{name:'clear-leaves-input',from:"setText('');",to:'/* fault injection: retained input */',oracle:async(p,e)=>{await p.getByTestId('score-input').fill('甲,60');await p.getByTestId('analyze-button').click();await p.getByTestId('clear-button').click();await e(p.getByTestId('score-input')).toHaveValue('');}},
{name:'invalid-line-number-off-by-one',from:'const lineNo = i + 1;',to:'const lineNo = i;',oracle:async(p,e)=>{await p.getByTestId('score-input').fill('甲,60\n\n坏行');await p.getByTestId('analyze-button').click();await e(p.getByTestId('invalid-item')).toContainText('第 3 行');}},
];
const results=[];
for(const v of variants){const source=files['/src/App.jsx'];if(source.split(v.from).length!==2)throw new Error('mutation mismatch '+v.name);await withFiles(files,v.oracle);const changed={...files,'/src/App.jsx':source.replace(v.from,v.to)};let violated=false;try{await withFiles(changed,v.oracle);}catch{violated=true;}if(!violated)throw new Error('invalid mutation '+v.name);const generated=await checkProject({files:changed,checks:a.checks});results.push({name:v.name,baselinePasses:true,independentRequirementViolated:true,missedByGeneratedChecks:generated.passed,generated});fs.writeFileSync(out+'/csv-mutations.json',JSON.stringify(results,null,2));console.log(v.name,'MISSED',generated.passed);}
