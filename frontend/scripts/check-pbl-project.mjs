// Compilation is host-only; student code runs in a disposable, unauthenticated browser.
import { createServer } from 'node:http';
import { createRequire } from 'node:module';
import { performance } from 'node:perf_hooks';
import { build } from 'esbuild';
import { chromium } from 'playwright';
import {runUiCheck} from './pbl-ui-check.mjs';
import { checkNativeProject } from './check-pbl-native.mjs';
const require = createRequire(import.meta.url);
const allowedFiles = ['/src/App.jsx', '/src/styles.css'];
const entry = `import React from 'react';import {createRoot} from 'react-dom/client';import App from '/src/App.jsx';import '/src/styles.css';createRoot(document.getElementById('root')).render(<App/>);`;

export async function checkProject({ files, checks, runtime }) {
  if(runtime){const {checkSandpackProject}=await import('./check-pbl-sandpack.mjs');return checkSandpackProject({files,checks,runtime});}
  const start = performance.now();
  const fail = message => ({ passed: false, results: checks.map(c => ({ caseId: c.id, status: 'failed', message })), durationMs: performance.now() - start });
  if (!files || Object.keys(files).sort().join() !== allowedFiles.slice().sort().join() ||
      Object.values(files).some(v => typeof v !== 'string') || Buffer.byteLength(JSON.stringify(files)) > 262144 ||
      !Array.isArray(checks) || !checks.length || checks.length > 64) throw new Error('Invalid project input');
  let compiled;
  try {
    compiled = await build({entryPoints:['/entry.jsx'],bundle:true,write:false,outdir:'out',platform:'browser',format:'iife',jsx:'automatic',logLevel:'silent',define:{'process.env.NODE_ENV':'"production"'},plugins:[{
      name:'fixed-project-files',setup(api){
        api.onResolve({filter:/.*/},args=>{
          if (args.namespace === 'file') return; // Trusted installed React internals only.
          if (args.path === '/entry.jsx' && args.kind === 'entry-point') return {path:args.path,namespace:'project'};
          if (args.path === 'react' || args.path === 'react/jsx-runtime' || (args.importer === '/entry.jsx' && args.path === 'react-dom/client')) return {path:require.resolve(args.path)};
          if (args.path === '/src/App.jsx' && args.importer === '/entry.jsx') return {path:args.path,namespace:'project'};
          if (['/src/styles.css','./styles.css'].includes(args.path)) return {path:'/src/styles.css',namespace:'project'};
          return {errors:[{text:'只允许 React 与项目样式导入'}]};
        });
        api.onLoad({filter:/.*/,namespace:'project'},args=>({contents:args.path === '/entry.jsx' ? entry : files[args.path],loader:args.path.endsWith('.css')?'css':'jsx'}));
      }
    }]});
  } catch { return fail('代码未能编译，请检查语法、默认导出与导入路径'); }
  const native=checks.filter(check=>check.engine==='sandpack-jest');
  if(native.length){
    if(native.some(check=>!check.source||check.source.length>32000||!/^[a-z][a-z0-9-]*$/.test(check.id))) throw new Error('Invalid native test');
    const nativeReport=await checkNativeProject({files,checks:native});
    const legacy=checks.filter(check=>check.engine!=='sandpack-jest');
    const legacyReport=legacy.length?await checkProject({files,checks:legacy}):{results:[]};
    const byId=new Map([...nativeReport.results,...legacyReport.results].map(result=>[result.caseId,result]));
    const results=checks.map(check=>byId.get(check.id));
    return {passed:results.every(result=>result.status==='passed'),results,durationMs:performance.now()-start};
  }
  const js = compiled.outputFiles.find(f=>f.path.endsWith('.js'))?.text || '';
  const css = compiled.outputFiles.find(f=>f.path.endsWith('.css'))?.text || '';
  const server = createServer((req,res)=>{
    // No dynamic reads or outbound proxy, only these in-memory assets.
    res.setHeader('Content-Security-Policy',"default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src data:; connect-src 'none'; frame-src 'none'; worker-src 'none'; base-uri 'none'; form-action 'none'");
    if(req.url === '/') {res.setHeader('Content-Type','text/html');res.end('<!doctype html><html><head><link rel="stylesheet" href="/app.css"></head><body><div id="root"></div><script src="/app.js"></script></body></html>');}
    else if(req.url === '/app.js'){res.setHeader('Content-Type','text/javascript');res.end(js);}
    else if(req.url === '/app.css'){res.setHeader('Content-Type','text/css');res.end(css);}
    else {res.statusCode=404;res.end();}
  });
  let browser;
  try {
    await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
    const origin = `http://127.0.0.1:${server.address().port}`;
    browser = await chromium.launch({headless:true,args:['--disable-dev-shm-usage']});
    const results=[];
    for(const check of checks){
      const viewport=check.viewport==='mobile'?{width:390,height:844}:check.viewport==='desktop'?{width:1280,height:800}:undefined;
      const context=await browser.newContext({serviceWorkers:'block',...(viewport?{viewport}:{})});
      context.setDefaultTimeout(1200);
      await context.route('**/*',route=>[origin+'/',origin+'/app.js',origin+'/app.css'].includes(route.request().url()) ? route.continue() : route.abort());
      await context.routeWebSocket('**/*',socket=>socket.close());
      const page=await context.newPage();
      const errors=[];
      page.on('pageerror',()=>errors.push('页面运行错误'));
      page.on('dialog',dialog=>void dialog.dismiss());
      try {
        await page.goto(origin,{waitUntil:'load',timeout:5000});
        results.push(await runUiCheck(page,check,async()=>{},errors));
      } catch(error) {results.push({caseId:check.id,status:'failed',message:String(error.message).slice(0,2000)});} finally {await context.close();}
    }
    return {passed:results.every(r=>r.status==='passed'),results,durationMs:performance.now()-start};
  } finally {await browser?.close();await new Promise(resolve=>server.close(resolve));}
}
if(process.argv[1] === new URL(import.meta.url).pathname){
  let input='';for await(const part of process.stdin){input+=part;if(input.length>2000000)throw new Error('Input too large');}
  process.stdout.write(JSON.stringify(await checkProject(JSON.parse(input))));
}
