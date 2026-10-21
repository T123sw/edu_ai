import fs from 'node:fs';
import {randomUUID} from 'node:crypto';
const base='http://127.0.0.1/backend';
async function call(path,method,body,token){const r=await fetch(base+path,{method,headers:{'Content-Type':'application/json',...(token?{Authorization:`Bearer ${token}`}:{})},...(body?{body:JSON.stringify(body)}:{})});if(!r.ok)throw new Error(`${path} ${r.status}: ${await r.text()}`);return r.json()}
const suffix=randomUUID().slice(0,8),password=randomUUID();
const auth=await call('/api/auth/register','POST',{username:'resource_e2e_'+suffix,password,role:'teacher'});
const id='resource-e2e-'+suffix;
const course=await call('/api/courses','POST',{id,title:'资源生成端到端验证 · Python 变量与列表',description:'仅用于资源生成验收。知识范围：Python 变量绑定对象；整数不可变；a=[1,2]; b=a 时 a 与 b 引用同一列表，b.append(3) 也改变 a 所见内容；b=a.copy() 创建浅拷贝，嵌套列表仍共享；判断别名与重新赋值的区别。面向入门学习者，使用中文。',icon:'BookOutlined',color:'#607b50'},auth.token);
await call(`/api/courses/${id}/knowledge-graph`,'PUT',{root:{id,label:course.title,children:[{id:id+'-variables',label:'Python 变量绑定、列表别名与浅拷贝',type:'knowledge_point',children:[]}]}},auth.token);
const room=await call(`/api/self-learning/courses/${id}`,'GET',null,auth.token);
fs.writeFileSync('/tmp/edu-resource-e2e-account.json',JSON.stringify({...auth,password,courseId:id,chapterId:room.chapters[0].id}),{mode:0o600});
fs.writeFileSync('/home/zxqs_ep/Edu_AI/docs/acceptance/2026-10-14-resource-tools-e2e/setup.json',JSON.stringify({courseId:id,chapterId:room.chapters[0].id,createdAt:new Date().toISOString(),setup:'Dedicated test account/course via real authenticated APIs; no generated-resource mocks or database overrides'},null,2));
console.log(JSON.stringify({courseId:id,chapterId:room.chapters[0].id}));
