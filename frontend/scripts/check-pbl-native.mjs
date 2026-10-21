import { createServer } from 'node:http';
import { performance } from 'node:perf_hooks';
import { build } from 'esbuild';
import { chromium } from 'playwright';

let harness;
export async function checkNativeProject({files,checks,runtime}, {timeout=70000,diagnostics=[]}={}) {
  const start=performance.now();
  if(!checks.length) throw new Error('No native tests supplied');
  // Build only trusted host code. Learner code is delivered as data to Sandpack.
  harness ||= build({entryPoints:['src/pbl/runtime/SandpackTestHarness.tsx'],bundle:true,write:false,
    jsx:'automatic',format:'iife',platform:'browser',logLevel:'silent',
    define:{'process.env.NODE_ENV':'"production"'}}).then(result=>result.outputFiles[0].text);
  const script=await harness;
  const server=createServer((req,res)=>{
    res.setHeader('Content-Security-Policy',"default-src 'none'; script-src 'self'; style-src 'unsafe-inline'; frame-src https://2-19-8-sandpack.codesandbox.io; img-src data:; base-uri 'none'; form-action 'none'");
    if(req.url==='/'){res.setHeader('Content-Type','text/html');res.end('<!doctype html><html><body><div id="root"></div><script src="/host.js"></script></body></html>');}
    else if(req.url==='/host.js'){res.setHeader('Content-Type','text/javascript');res.end(script);}
    else{res.statusCode=404;res.end();}
  });
  let browser;
  try {
    await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
    const origin=`http://127.0.0.1:${server.address().port}`;
    browser=await chromium.launch({headless:true,args:['--disable-dev-shm-usage']});
    const context=await browser.newContext({serviceWorkers:'block'});
    await context.route('**/*',route=>{
      const url=new URL(route.request().url());
      const host=url.hostname;
      const assetHost=['2-19-8-sandpack.codesandbox.io','sandpack-cdn-v2.codesandbox.io','sandpack-cdn.codesandbox.io',
        'prod-packager-packages.codesandbox.io','aiwi8rnkp5.execute-api.eu-west-1.amazonaws.com',
        'unpkg.com','cdnjs.cloudflare.com','cdn.jsdelivr.net','data.jsdelivr.com'].includes(host);
      const allowed=(url.origin===origin&&['/','/host.js'].includes(url.pathname))||(url.protocol==='https:'&&assetHost);
      if(!allowed) diagnostics.push(`blocked: ${url.origin}${url.pathname}`);
      return allowed?route.continue():route.abort();
    });
    await context.routeWebSocket('**/*',socket=>socket.close());
    const page=await context.newPage();
    if(process.env.PBL_NATIVE_TRACE==='1') {
      page.on('console',message=>{if(message.text().startsWith('PBL_EVENT:'))diagnostics.push(message.text());});
      await page.addInitScript(()=>window.addEventListener('message',event=>{
        if(event.data?.type==='test'||event.data?.type==='action'||event.data?.channel==='pbl-jest-hooks-v1') console.log('PBL_EVENT:'+JSON.stringify({data:event.data,origin:event.origin,top:window===window.top,iframeSource:[...document.querySelectorAll('iframe')].some(frame=>frame.contentWindow===event.source)}));
      }));
    }
    page.on('pageerror',error=>diagnostics.push(error.message));
    page.on('requestfailed',request=>diagnostics.push(`request failed: ${request.url().split('?')[0]}`));
    page.on('dialog',dialog=>void dialog.dismiss());
    await page.goto(origin,{waitUntil:'load',timeout:10000});
    await page.evaluate(input=>window.startPblTests(input),{files,checks,runtime});
    // An empty/missing spec, skipped test or file error is mapped to failure by
    // the shared result adapter. No onComplete callback means no run evidence.
    try { await page.waitForFunction(()=>window.pblTestReport,undefined,{timeout}); }
    catch(error){diagnostics.push((await page.locator('body').innerText()).slice(0,3000));throw error;}
    const report=await page.evaluate(()=>window.pblTestReport);
    return {...report,durationMs:performance.now()-start};
  } finally {
    await browser?.close();
    await new Promise(resolve=>server.close(resolve));
  }
}
