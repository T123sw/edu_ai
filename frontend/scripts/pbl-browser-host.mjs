// Bundle only trusted UI. Sandpack executes learner sources in an anonymous browser.
import {createServer} from 'node:http';
import {build} from 'esbuild';
import {chromium} from 'playwright';
const scripts=new Map(),assetCache=new Map();let cachedBytes=0;
const assetHosts=new Set(['2-19-8-sandpack.codesandbox.io','sandpack-cdn-v2.codesandbox.io','sandpack-cdn.codesandbox.io','prod-packager-packages.codesandbox.io','aiwi8rnkp5.execute-api.eu-west-1.amazonaws.com','unpkg.com','cdnjs.cloudflare.com','cdn.jsdelivr.net','data.jsdelivr.com','nodebox-runtime.codesandbox.io','sandpack-static-server.codesandbox.io','registry.npmjs.org']);
export async function browserHost(entry){
  if(!scripts.has(entry)) scripts.set(entry,build({entryPoints:[entry],bundle:true,write:false,jsx:'automatic',format:'iife',platform:'browser',logLevel:'silent',define:{'process.env.NODE_ENV':'"production"'}}).then(r=>r.outputFiles[0].text));
  const script=await scripts.get(entry);
  const server=createServer((req,res)=>{
    if(req.url==='/host.js'){res.setHeader('Content-Type','text/javascript');res.end(script)}
    else if(req.url==='/'){res.setHeader('Content-Type','text/html');res.end('<!doctype html><html><head><style>html,body,#root{margin:0;width:100%;height:100%}</style></head><body><div id="root"></div><script src="/host.js"></script></body></html>')}
    else{res.statusCode=404;res.end()}
  });
  await new Promise(r=>server.listen(0,'127.0.0.1',r));
  const origin=`http://127.0.0.1:${server.address().port}`;
  let browser;
  try{browser=await chromium.launch({headless:true,args:['--disable-dev-shm-usage']})}
  catch(error){await new Promise(r=>server.close(r));throw error}
  return {origin,browser,async newContext(options={}){
    const context=await browser.newContext(options);
    // Context routing also intercepts outgoing ServiceWorker fetches. Nodebox's
    // virtual HTTP responses stay in its worker and never reach the network.
    // https://playwright.dev/docs/service-workers#network-events-and-routing
    await context.route('**/*',async route=>{
      const url=new URL(route.request().url());
      const local=url.origin===origin&&['/','/host.js'].includes(url.pathname);
      const asset=url.protocol==='https:'&&(!url.port||url.port==='443')&&(assetHosts.has(url.hostname)||/^[a-z0-9-]+\.(?:nodebox|sandpack-static-server)\.codesandbox\.io$/.test(url.hostname));
      if(!local&&!asset)return route.abort();
      // Routing disables Chromium's HTTP cache. Cache immutable compiler/CDN
      // JavaScript explicitly so each fresh check need not download it again.
      const cacheable=asset&&route.request().method()==='GET'&&/\.(?:js|mjs|css)$/.test(url.pathname)&&!url.hostname.includes('nodebox')&&!url.hostname.includes('sandpack-static-server');
      if(!cacheable)return route.continue();
      const key=url.href;
      if(!assetCache.has(key))assetCache.set(key,(async()=>{
        try{const response=await route.fetch({maxRedirects:0,timeout:20000});
          if(response.status()!==200)return null;
          const body=await response.body();if(body.length>10000000||cachedBytes+body.length>64000000)return null;
          cachedBytes+=body.length;return {status:200,headers:response.headers(),body};
        }catch{return null}
      })());
      const cached=await assetCache.get(key);
      if(!cached){assetCache.delete(key);return route.continue()}
      return route.fulfill(cached);
    });
    await context.routeWebSocket('**/*',socket=>socket.close());
    return context;
  },async close(){await browser.close();await new Promise(r=>server.close(r))}};
}
