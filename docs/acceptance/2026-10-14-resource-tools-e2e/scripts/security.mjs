import fs from 'node:fs';import assert from 'node:assert/strict';import {randomUUID} from 'node:crypto';
const out='/home/zxqs_ep/Edu_AI/docs/acceptance/2026-10-14-resource-tools-e2e';const account=JSON.parse(fs.readFileSync('/tmp/edu-resource-e2e-account.json'));
const r=await fetch('http://127.0.0.1/backend/api/auth/register',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:'resource_e2e_other_'+randomUUID().slice(0,8),password:randomUUID(),role:'student'})});assert(r.ok);const other=await r.json();
fs.writeFileSync('/tmp/edu-resource-e2e-other.json',JSON.stringify(other),{mode:0o600});
const listing=await(await fetch('http://127.0.0.1/backend/api/personal-studio',{headers:{Authorization:`Bearer ${account.token}`}})).json();
const results=[];
for(const resource of listing.resources){const path=`/api/personal-studio/resources/${resource.material_type}/${resource.material_id}`;for(const suffix of resource.material_type==='podcast'?['','/audio']:['']){const response=await fetch('http://127.0.0.1/backend'+path+suffix,{headers:{Authorization:`Bearer ${other.token}`}});assert.equal(response.status,404);results.push({kind:resource.material_type,audio:!!suffix,otherUserStatus:response.status});}}
const removed=await fetch('http://127.0.0.1/backend/api/personal-studio/resources/scenario/diagnostic',{headers:{Authorization:`Bearer ${account.token}`}});assert.equal(removed.status,404);
fs.writeFileSync(out+'/privacy.json',JSON.stringify({results,diagnosticRemoved:true},null,2));console.log(JSON.stringify(results));
