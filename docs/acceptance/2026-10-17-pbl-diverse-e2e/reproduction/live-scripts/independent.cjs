const fs=require('node:fs'),{withFiles}=require('./runtime.cjs');
const root='/tmp/pbl-diverse-20261017',out='/home/zxqs_ep/Edu_AI/docs/acceptance/2026-10-17-pbl-diverse-e2e';
const read=p=>JSON.parse(fs.readFileSync(p));
(async()=>{const pending=new Set(['kanban','quiz','expense','csv','seats','wizard']),results=[];
 const until=Date.now()+40*60*1000;
 while(pending.size&&Date.now()<until){let acted=false;
 for(const name of pending){const d=root+'/matrix_'+name;if(!fs.existsSync(d+'/detail.json'))continue;const detail=read(d+'/detail.json');if(!detail.artifact){pending.delete(name);results.push({name,skipped:true,reason:'generation failed'});acted=true;continue;}
 const oracle=root+'/oracles/'+name+'.cjs';if(!fs.existsSync(oracle))continue;
 const files=read(d+'/private.json').candidate_private.completed.at(-1).candidate.referenceFiles;const scenarios=[];const started=Date.now();
 try{await withFiles(files,async(page,expect)=>{await require(oracle)(page,expect,scenarios);await page.screenshot({path:out+'/'+name+'-independent.png',fullPage:true});});results.push({name,passed:true,scenarios,seconds:(Date.now()-started)/1000});}
 catch(e){results.push({name,passed:false,error:e.stack,scenarios,seconds:(Date.now()-started)/1000});}
 pending.delete(name);acted=true;console.log(JSON.stringify(results.at(-1)));fs.writeFileSync(out+'/independent.json',JSON.stringify(results,null,2));}
 if(!acted)await new Promise(r=>setTimeout(r,1000));
 }fs.writeFileSync(out+'/independent.json',JSON.stringify(results,null,2));})();
