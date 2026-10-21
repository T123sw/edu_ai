const frontend=require('node:path').resolve(__dirname,'../../../../frontend');
const {createServer}=require('node:http');
const {build}=require(frontend+'/node_modules/esbuild');
const {chromium,expect}=require(frontend+'/node_modules/playwright/test');

async function withFiles(files,run){
 const entry="import React from 'react';import {createRoot} from 'react-dom/client';import App from '/src/App.jsx';import '/src/styles.css';createRoot(document.getElementById('root')).render(<App/>);";
 const compiled=await build({entryPoints:['/entry.jsx'],bundle:true,write:false,outdir:'out',platform:'browser',format:'iife',jsx:'automatic',logLevel:'silent',define:{'process.env.NODE_ENV':'"production"'},plugins:[{name:'fixture',setup(api){
  api.onResolve({filter:/.*/},a=>{if(a.namespace==='file')return;if(a.path==='/entry.jsx')return {path:a.path,namespace:'project'};if(['react','react/jsx-runtime','react-dom/client'].includes(a.path))return {path:require.resolve(a.path,{paths:[frontend]})};if(a.path==='/src/App.jsx')return {path:a.path,namespace:'project'};if(['/src/styles.css','./styles.css'].includes(a.path))return {path:'/src/styles.css',namespace:'project'};return {errors:[{text:'unsupported import'}]};});
  api.onLoad({filter:/.*/,namespace:'project'},a=>({contents:a.path==='/entry.jsx'?entry:files[a.path],loader:a.path.endsWith('.css')?'css':'jsx'}));
 }}]});
 const js=compiled.outputFiles.find(f=>f.path.endsWith('.js')).text,css=compiled.outputFiles.find(f=>f.path.endsWith('.css'))?.text||'';
 const server=createServer((req,res)=>{res.setHeader('Content-Security-Policy',"default-src 'none';script-src 'self';style-src 'self' 'unsafe-inline';img-src data:;connect-src 'none'");if(req.url==='/'){res.setHeader('Content-Type','text/html');res.end('<!doctype html><link rel="stylesheet" href="/app.css"><div id="root"></div><script src="/app.js"></script>');}else if(req.url==='/app.js'){res.setHeader('Content-Type','text/javascript');res.end(js);}else if(req.url==='/app.css'){res.setHeader('Content-Type','text/css');res.end(css);}else {res.statusCode=404;res.end();}});
 let browser;
 try{await new Promise(r=>server.listen(0,'127.0.0.1',r));const origin='http://127.0.0.1:'+server.address().port;
 browser=await chromium.launch({headless:true,args:['--disable-dev-shm-usage']});const context=await browser.newContext({serviceWorkers:'block'});await context.route('**/*',r=>r.request().url().startsWith(origin+'/')?r.continue():r.abort());const page=await context.newPage();page.setDefaultTimeout(5000);await page.goto(origin);await expect(page.locator('#root')).not.toBeEmpty();return await run(page,expect);
 }finally{await browser?.close();await new Promise(r=>server.close(r));}
}
module.exports={withFiles};
