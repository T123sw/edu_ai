// Native HF_MEDIA_ENGINE adapter: the upstream workflow owns scripts and timing.
import {readFileSync,writeFileSync} from 'node:fs';
import http from 'node:http';
import {spawnSync} from 'node:child_process';
const args=process.argv.slice(2);
const flag=(key, fallback)=>{const i=args.indexOf('--'+key);return i<0?fallback:args[i+1]};
const request=JSON.parse(readFileSync(flag('request'),'utf8'));
const only=flag('only','tts,bgm,sfx').split(',');
const data=JSON.stringify({request,project:flag('hyperframes','.'),only:'tts'});
const response=only.includes('tts')?await new Promise((resolve,reject)=>{
 const r=http.request({socketPath:process.env.EDU_HF_AUDIO_SOCKET,path:'/audio',method:'POST',headers:{'Content-Type':'application/json','Content-Length':Buffer.byteLength(data)}},res=>{
  let body='';res.on('data',c=>body+=c);res.on('end',()=>res.statusCode===200?resolve(JSON.parse(body)):reject(Error(body)));
 });r.on('error',reject);r.end(data);
}):{};
const out=flag('out');let previous={};try{previous=JSON.parse(readFileSync(out,'utf8'))}catch(e){if(e.code!=='ENOENT')throw e}
writeFileSync(out,JSON.stringify({...previous,...response},null,2));
const native=only.filter(k=>k!=='tts');
if(native.length){
 const forwarded=args.filter((_,i)=>args[i]!=='--only'&&args[i-1]!=='--only');
 const p=spawnSync(process.execPath,[process.env.EDU_HF_NATIVE_AUDIO_ENGINE,...forwarded,'--only',native.join(',')],{stdio:'inherit'});
 if(p.status!==0)process.exit(p.status??1);
}
console.log(JSON.stringify({provider:'host',voices:response.voices?.length,output:out}));
